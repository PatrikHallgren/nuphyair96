#!/usr/bin/env python3
"""Persistent NDJSON worker for the Air96 Omarchy plugin.

One process serves every monitor. Theme changes come from inotify on the
active Omarchy theme directory. Modifier state is optional and only records
Shift, Ctrl, Alt, and Super.
"""

import ctypes
import json
import os
from pathlib import Path
import selectors
import socket
import struct
import subprocess
import sys
import time

from air96_audio import MusicSession
from air96_backend import Backend, file_lock
from air96_binds import parse_hyprctl_binds
from air96_ha import HomeAssistantError
from air96_hid import EvdevModifiers, HidError, HidTransport, find_devices, find_event_nodes
from air96_profiles import ProfileError
from air96_protocol import ProtocolError
from air96_theme import THEME_DIR

FALLBACK_SECONDS = 60
MAX_REQUEST = 262144


def execute(backend, request):
    action = request.get("action") or "status"
    config = request.get("config") if isinstance(request.get("config"), dict) else {}
    try:
        if action == "apply":
            backend.apply_lighting(config, force=True)
        elif action == "sync":
            backend.sync(force=bool(config.get("force")))
        elif action == "keymap-load":
            backend.load_keymap()
        elif action == "keymap-apply":
            backend.apply_keymap(config.get("changes"))
        elif action == "settings":
            backend.update_settings(config)
        elif action == "ha-push":
            backend.push_home_assistant()
        elif action != "status":
            raise ValueError("Unknown action")
    except (ValueError, ProtocolError, HomeAssistantError, ProfileError, HidError, OSError, TimeoutError) as exc:
        backend.error = str(exc)[:600]
    return backend.snapshot(include_keymap=action.startswith("keymap"))


def refresh_device(backend):
    devices = find_devices()
    if len(devices) > 1:
        _close_transport(backend)
        backend.set_device(None, None, "ambiguous")
        return
    if not devices:
        _close_transport(backend)
        backend.set_device(None, None, "not-found")
        return
    device = devices[0]
    identity = f"{device['vid']:04x}:{device['pid']:04x}:{device['path']}"
    if identity == backend.device_identity and backend.transport is not None:
        return
    _close_transport(backend)
    if not os.access(device["path"], os.R_OK | os.W_OK):
        backend.set_device(device, None, "hid-permission")
        return
    try:
        transport = HidTransport(device["path"])
    except OSError as exc:
        backend.set_device(device, None, "hid-permission")
        backend.error = str(exc)[:300]
        return
    backend.set_device(device, transport, "")


def _close_transport(backend):
    transport = backend.transport
    if transport is not None:
        transport.close()
        backend.transport = None


def refresh_binds(backend):
    try:
        result = subprocess.run(["hyprctl", "binds", "-j"], capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    try:
        backend.binds = parse_hyprctl_binds(result.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        return False
    return True


def refresh_window(backend):
    try:
        result = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode != 0 or not result.stdout.strip():
        return
    try:
        window = json.loads(result.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return
    if isinstance(window, dict):
        backend.window_class = str(window.get("class") or "")
        backend.window_title = str(window.get("title") or "")


def hypr_socket_path():
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    candidates = []
    if signature:
        candidates.append(Path(runtime) / "hypr" / signature / ".socket2.sock")
        candidates.append(Path("/tmp/hypr") / signature / ".socket2.sock")
    base = Path(runtime) / "hypr"
    if base.is_dir():
        candidates.extend(child / ".socket2.sock" for child in base.iterdir())
    for path in candidates:
        if path.exists():
            return path
    return None


class HyprEvents:
    def __init__(self):
        self.socket = None
        self.buffer = b""

    def connect(self):
        self.close()
        path = hypr_socket_path()
        if path is None:
            return False
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.setblocking(False)
        try:
            sock.connect(os.fspath(path))
        except OSError:
            sock.close()
            return False
        self.socket = sock
        return True

    def fileno(self):
        return self.socket.fileno() if self.socket else -1

    def drain(self, backend):
        if not self.socket:
            return False
        closed = False
        while True:
            try:
                chunk = self.socket.recv(65536)
            except BlockingIOError:
                break
            except OSError:
                closed = True
                break
            if not chunk:
                closed = True
                break
            self.buffer += chunk
        changed = False
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace")
            if ">>" not in text:
                continue
            event, payload = text.split(">>", 1)
            if event == "activewindow":
                window_class, _, title = payload.partition(",")
                backend.window_class = window_class
                backend.window_title = title
                changed = True
            elif event == "submap":
                backend.submap = payload
                changed = True
            elif event == "configreloaded":
                refresh_binds(backend)
                changed = True
        if closed:
            # Parse first. close() drops a partial line from the dead socket.
            self.close()
        return changed

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.buffer = b""


class ThemeWatch:
    """inotify on the theme directory and /dev, same idea as omarchy-nuphy."""

    MASK = (
        0x00000002 | 0x00000004 | 0x00000008 | 0x00000040 | 0x00000080
        | 0x00000100 | 0x00000200 | 0x00000400 | 0x00000800
    )

    def __init__(self, theme_dir):
        self.theme_dir = Path(theme_dir)
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_init1.argtypes = (ctypes.c_int,)
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32)
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.libc.inotify_rm_watch.argtypes = (ctypes.c_int, ctypes.c_int)
        self.libc.inotify_rm_watch.restype = ctypes.c_int
        self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 failed")
        self.kinds = {}
        self.arm()

    def arm(self):
        paths = [self.theme_dir, self.theme_dir.parent, self.theme_dir.parent.parent, Path("/dev")]
        current = {}
        for path in paths:
            if not path.exists():
                continue
            watch = self.libc.inotify_add_watch(self.fd, os.fsencode(path), self.MASK)
            if watch >= 0:
                current[watch] = "device" if path == Path("/dev") else "theme"
        for watch in self.kinds.keys() - current.keys():
            self.libc.inotify_rm_watch(self.fd, watch)
        self.kinds = current

    def drain(self):
        changed = set()
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            offset = 0
            while offset + 16 <= len(data):
                watch, mask, _, length = struct.unpack_from("iIII", data, offset)
                name = data[offset + 16:offset + 16 + length].split(b"\0", 1)[0]
                offset += 16 + length
                kind = self.kinds.get(watch)
                if mask & 0x00004000:
                    changed.update(("theme", "device"))
                elif kind == "theme" and name in (b"", b"keyboard.rgb", b"colors.toml", b"theme", b"current"):
                    changed.add("theme")
                elif kind == "device" and name.startswith(b"hidraw"):
                    changed.add("device")
                if mask & 0x00008000:
                    self.kinds.pop(watch, None)
        return changed

    def close(self):
        os.close(self.fd)


_REVISION = None


def worker_revision():
    global _REVISION
    if _REVISION is None:
        from air96_backend import checkout_revision
        _REVISION = checkout_revision(Path(__file__).resolve().parent)
    return _REVISION


def publish_worker(backend, session):
    """Heartbeat so `status` can see the process that actually drives the keys."""
    capture = getattr(session, "capture", None)
    levels = getattr(session, "last_levels", None) or {}
    script = Path(__file__).resolve()
    payload = {
        "pid": os.getpid(),
        "script": str(script),
        "root": str(script.parent),
        "revision": worker_revision(),
        "updated": time.time(),
        "pushConfigured": bool(backend.config["per_key"]["push_to_keyboard"]),
        "perKey": bool(backend.per_key),
        "musicEnabled": bool(backend.config["music"]["enabled"]),
        "musicError": backend.music_error,
        "musicRunning": bool(getattr(session, "running", False)),
        "recorder": list(getattr(capture, "command", []) or []),
        "stalled": bool(getattr(capture, "stalled", False)),
        "bytes": int(getattr(capture, "bytes_total", 0) or 0),
        "rms": levels.get("rms") if isinstance(levels, dict) else None,
        "silent": levels.get("silent") if isinstance(levels, dict) else None,
        "held": backend.held,
    }
    path = backend.state_dir / "worker.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def drive_lights(backend, session, state, now):
    """Resend highlights before the firmware timeout, and stream music frames."""
    backend.reload_if_external()
    music = bool(backend.config["music"]["enabled"])
    pushing = bool(backend.config["per_key"]["push_to_keyboard"] and backend.per_key and backend.transport)
    if music:
        if state["music"] and not session.running:
            state["music"] = False
            state["retry"] = now + 2
        if not state["music"]:
            if now < state["retry"]:
                return
            try:
                session.start()
            except OSError as exc:
                backend.music_error = str(exc)[:300]
                state["retry"] = now + 2
                return
            state["music"] = True
            backend.music_error = ""
        try:
            levels = session.poll()
        except OSError as exc:
            backend.music_error = str(exc)[:300]
            levels = None
        if session.error:
            backend.music_error = session.error
        elif levels is not None:
            backend.music_error = ""
        interval = 0.05 if backend.per_key else 0.25
        if levels is not None and now - state["last_music"] >= interval:
            try:
                with file_lock(backend.state_dir):
                    backend.push_music(levels)
            except (ProtocolError, OSError, HidError, TimeoutError) as exc:
                backend.music_error = str(exc)[:300]
            state["last_music"] = now
        elif pushing and levels is None and now - backend.last_direct >= 0.4:
            # Not enough PCM yet. A probe holds the overlay. A gap longer than
            # 2 seconds, or a clear (0xA8), is what flashes the normal effect back.
            try:
                with file_lock(backend.state_dir):
                    backend.keepalive_overlay()
            except (ProtocolError, OSError, HidError, TimeoutError) as exc:
                backend.music_error = str(exc)[:300]
        state["push"] = pushing
        return
    if state["music"]:
        session.stop()
        state["music"] = False
        try:
            with file_lock(backend.state_dir):
                backend.release_overlay()
        except (ProtocolError, OSError, HidError, TimeoutError) as exc:
            backend.error = str(exc)[:300]
        state["push"] = pushing
        return
    if state["push"] and not pushing and backend.frame_kind == "highlight":
        try:
            with file_lock(backend.state_dir):
                backend.clear_per_key()
                if backend.transport is not None:
                    backend.apply_lighting(force=True, push_ha=False)
        except (ProtocolError, OSError, HidError, TimeoutError) as exc:
            backend.error = str(exc)[:300]
    state["push"] = pushing
    pushed = False
    if pushing and now - state.get("last_mods", 0) >= 0.08:
        state["last_mods"] = now
        mods = backend.read_keyboard_mods()
        if mods is not None and mods != backend.held:
            try:
                with file_lock(backend.state_dir):
                    backend.push_per_key()
                pushed = True
            except (ProtocolError, OSError, HidError, TimeoutError) as exc:
                backend.error = str(exc)[:300]
    if pushing and not pushed and now - backend.last_direct >= 0.9:
        try:
            with file_lock(backend.state_dir):
                backend.push_per_key()
        except (ProtocolError, OSError, HidError, TimeoutError) as exc:
            backend.error = str(exc)[:300]


def serve(backend=None, stdin=None):
    backend = backend or Backend()
    source = sys.stdin if stdin is None else stdin
    backend.state_dir.mkdir(parents=True, exist_ok=True)
    with file_lock(backend.state_dir):
        pass  # Fail fast if another settings writer is wedged; the lock is per call below.
    with (backend.state_dir / "worker.lock").open("w") as singleton:
        try:
            import fcntl
            fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("An Air96 worker is already running") from exc
        refresh_device(backend)
        refresh_binds(backend)
        refresh_window(backend)
        if backend.config["lighting"]["follow_theme"] and backend.transport is not None:
            with file_lock(backend.state_dir):
                execute(backend, {"action": "sync", "config": {"force": True}})
        selector = selectors.DefaultSelector()
        selector.register(source, selectors.EVENT_READ, "input")
        watcher = None
        hypr = HyprEvents()
        modifiers = EvdevModifiers()
        try:
            watcher = ThemeWatch(backend.theme_path or THEME_DIR)
            selector.register(watcher.fd, selectors.EVENT_READ, "watch")
        except OSError:
            watcher = None
        if hypr.connect():
            selector.register(hypr.socket, selectors.EVENT_READ, "hypr")
        if backend.config["modifiers"]["enabled"]:
            opened = modifiers.open_nodes(find_event_nodes())
            backend.modifier_permission = modifiers.permission
            for fd in opened:
                selector.register(fd, selectors.EVENT_READ, "keys")
        else:
            backend.modifier_permission = ""
        pending = set()
        deadline = None
        buffer = b""
        next_discovery = time.monotonic() + FALLBACK_SECONDS
        session = MusicSession()
        light_state = {"music": False, "push": False, "last_music": 0.0, "retry": 0.0}

        def emit(request):
            with file_lock(backend.state_dir):
                result = execute(backend, request)
            result["requestId"] = request.get("id")
            print(json.dumps(result, sort_keys=True), flush=True)
            return result

        emit({"action": "status"})
        while True:
            timeout = 1.0
            if backend.config["music"]["enabled"]:
                timeout = 0.05
            elif backend.config["per_key"]["push_to_keyboard"] and backend.per_key:
                timeout = 0.5
            if deadline is not None:
                timeout = min(timeout, max(0, deadline - time.monotonic()))
            timeout = min(timeout, max(0, next_discovery - time.monotonic()))
            events = selector.select(timeout)
            for key, _ in events:
                if key.data == "watch":
                    pending.update(watcher.drain())
                    if pending and deadline is None:
                        deadline = time.monotonic() + 0.2
                elif key.data == "hypr":
                    if hypr.drain(backend):
                        pending.add("highlight")
                        if deadline is None:
                            deadline = time.monotonic() + 0.05
                elif key.data == "keys":
                    if modifiers.drain():
                        backend.held = modifiers.mask
                        pending.add("highlight")
                        if deadline is None:
                            deadline = time.monotonic() + 0.05
                else:
                    chunk = os.read(source.fileno(), MAX_REQUEST)
                    if not chunk:
                        session.stop()
                        _close_transport(backend)
                        modifiers.close()
                        hypr.close()
                        if watcher:
                            watcher.close()
                        return
                    buffer += chunk
                    if len(buffer) > MAX_REQUEST:
                        raise ValueError("Request exceeds maximum size")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        request = None
                        try:
                            request = json.loads(line)
                            if not isinstance(request, dict):
                                raise ValueError("Invalid worker request")
                            if request.get("action") not in (None, "status", "apply", "sync", "keymap-load", "keymap-apply", "settings", "ha-push"):
                                raise ValueError("Invalid worker request")
                            if request.get("action") not in (None, "status"):
                                refresh_device(backend)
                            emit(request)
                        except (ValueError, TypeError, json.JSONDecodeError) as exc:
                            body = {"error": str(exc)[:600], "protocolError": True}
                            if isinstance(request, dict):
                                body["requestId"] = request.get("id")
                            print(json.dumps(body), flush=True)
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                if "device" in pending:
                    refresh_device(backend)
                if "theme" in pending or "device" in pending:
                    if backend.config["lighting"]["follow_theme"]:
                        emit({"action": "sync"})
                    else:
                        emit({"action": "status"})
                elif "highlight" in pending:
                    if backend.config["per_key"]["push_to_keyboard"] and backend.per_key:
                        try:
                            with file_lock(backend.state_dir):
                                backend.push_per_key()
                        except (ProtocolError, OSError, HidError) as exc:
                            backend.error = str(exc)[:600]
                    emit({"action": "status"})
                pending.clear()
                deadline = None
                if watcher:
                    watcher.arm()
            if now >= next_discovery:
                refresh_device(backend)
                refresh_binds(backend)
                if watcher:
                    watcher.arm()
                if backend.config["lighting"]["follow_theme"] and backend.transport is not None and not backend.applied_signature:
                    emit({"action": "sync"})
                next_discovery = now + FALLBACK_SECONDS
                if hypr.socket is None and hypr.connect():
                    selector.register(hypr.socket, selectors.EVENT_READ, "hypr")
            drive_lights(backend, session, light_state, now)
            try:
                publish_worker(backend, session)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        serve()
    except Exception as exc:  # noqa: BLE001 - the shell restarts the worker from this message
        print(str(exc)[:600], file=sys.stderr)
        raise
