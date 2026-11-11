#!/usr/bin/env python3
"""One-shot Air96 commands for theme hooks and setup checks.

``sync`` writes the theme color only when theme follow is enabled. It is safe
to call from an Omarchy theme hook before the bar plugin is running.
"""

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

from air96_backend import Backend, file_lock
from air96_ha import HomeAssistantError, prepare_token
from air96_hid import HidError, set_debug
from air96_protocol import ProtocolError
from air96_profiles import import_vscode_keybindings
from air96_worker import refresh_device


def build(args):
    backend = Backend()
    if args.theme_dir:
        backend.theme_path = args.theme_dir
    return backend


def command_status(backend, _args):
    from air96_backend import describe_runtime
    with file_lock(backend.state_dir):
        refresh_device(backend)
        from air96_worker import refresh_binds
        refresh_binds(backend)
        mods = backend.read_keyboard_mods()
        backend.mods_from_keyboard = mods is not None
        if mods is not None:
            backend.held = mods
        body = backend.snapshot()
        report = describe_runtime(backend)
        body["diagnosis"] = report["lines"]
        body["runtime"] = report["runtime"]
        print(json.dumps(body, indent=2, sort_keys=True))
    for line in report["lines"]:
        print(line, file=sys.stderr)


def command_devices(_backend, _args):
    from air96_hid import find_devices
    print(json.dumps(find_devices(), indent=2))


def command_sync(backend, args):
    with file_lock(backend.state_dir):
        refresh_device(backend)
        backend.sync(force=args.force)
        print(backend.message or backend.error or "ok")
        if backend.error:
            return 1
    return 0


def command_apply(backend, args):
    patch = {}
    if args.hex:
        patch["hex"] = args.hex
    if args.effect is not None:
        patch["effect"] = args.effect
    if args.brightness is not None:
        patch["brightness"] = args.brightness
    if args.speed is not None:
        patch["speed"] = args.speed
    if args.follow is not None:
        patch["follow_theme"] = args.follow
    with file_lock(backend.state_dir):
        refresh_device(backend)
        backend.apply_lighting(patch, force=True)
        print(backend.message or backend.error)
        if backend.error:
            return 1
    return 0


def command_music(backend, args):
    if args.state == "run":
        if args.music_debug:
            set_debug(True)
        return command_music_run(backend)
    patch = {"enabled": args.state == "on"}
    if args.effect:
        patch["effect"] = args.effect
    with file_lock(backend.state_dir):
        backend.update_settings({"music": patch})
    print(backend.message or "ok")
    if args.state == "on":
        print("Music mode is saved. The bar worker plays it from the speaker monitor.")
        print("If the keys stay still: python3 air96_cli.py music run --debug")
    return 0


def command_push(backend, args):
    enabled = args.state == "on"
    with file_lock(backend.state_dir):
        backend.update_settings({"per_key": {"push_to_keyboard": enabled, "enabled": True}})
    print(backend.message or "ok")
    if enabled:
        print("Per-key push is on. Super highlights use the keyboard's modifier report. The input udev rule is not required.")
        print("Turn music off first if the visualizer is using the keys: python3 air96_cli.py music off")
    else:
        print("Per-key push is off. The worker will not send highlight colors.")
    return 0


def run_music_debug(backend, session, cycles=None, pause=None, emit=print):
    """Print levels and push frames. ``cycles`` bounds a test; a live run stops on Ctrl-C."""
    emit("Recording: " + " ".join(getattr(session.capture, "command", []) or []))
    emit("Source is the speaker monitor, not the microphone. Silence should go dark. A beat should move rms and bass.")
    count = 0
    while cycles is None or count < cycles:
        levels = session.poll()
        capture = session.capture
        bytes_total = getattr(capture, "bytes_total", 0)
        if levels is None:
            emit(f"waiting bytes={bytes_total} stalled={getattr(capture, 'stalled', False)} {session.error}")
        else:
            sent = "keyboard not connected"
            if backend.transport is not None:
                try:
                    backend.push_music(levels)
                    sent = backend.message or "sent"
                except (OSError, TimeoutError, ProtocolError, HidError) as exc:
                    sent = str(exc)[:200]
            emit(
                "rms={rms:.3f} bass={bass:.3f} loud={loud:.3f} silent={silent} bytes={bytes} {sent}".format(
                    rms=float(levels.get("rms") or 0),
                    bass=float(levels.get("bass") or 0),
                    loud=float(levels.get("loudness") or 0),
                    silent=bool(levels.get("silent")),
                    bytes=bytes_total,
                    sent=sent,
                )
            )
        count += 1
        if cycles is not None and count >= cycles:
            break
        if pause:
            pause()
    return count


def command_music_run(backend):
    from air96_audio import MusicSession
    refresh_device(backend)
    session = MusicSession()
    try:
        session.start()
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        run_music_debug(backend, session, pause=lambda: __import__("time").sleep(0.1))
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        session.stop()
        if backend.transport is not None:
            try:
                with file_lock(backend.state_dir):
                    backend.release_overlay()
            except (OSError, TimeoutError, ProtocolError, HidError):
                pass
    return 0


def command_ha_token(backend, args):
    raw = getpass.getpass("Home Assistant token: ")
    token = prepare_token(raw)
    section = backend.config["home_assistant"]
    path = Path(args.file or section["token_file"] or (backend.config_path.parent / "ha-token"))
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, (token + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)
    with file_lock(backend.state_dir):
        backend.update_settings({"home_assistant": {"token_file": str(path), "token": ""}})
    print(f"Saved Home Assistant token to {path}")
    env_name = section["token_env"] or "HA_TOKEN"
    if backend.environ.get(env_name):
        print(f"{env_name} is set and overrides the token file.", file=sys.stderr)
    return 0


def command_ha_test(backend, _args):
    with file_lock(backend.state_dir):
        result = backend.push_home_assistant()
    if result.get("skipped"):
        print(backend.message)
        return 0
    print(f"Home Assistant returned HTTP {result['status']}")
    body = (result.get("body") or "").strip()
    if body:
        print(body[:400])
    return 0


def command_import_vscode(_backend, args):
    text = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    profile = import_vscode_keybindings(text, profile_id=args.id, name=args.name, classes=args.match_class)
    json.dump(profile, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def parser():
    program = argparse.ArgumentParser(prog="air96_cli.py", description="NuPhy Air96 V2 commands for Omarchy")
    program.add_argument("--theme-dir", default="", help="Override the active Omarchy theme directory")
    program.add_argument("--debug", action="store_true", help="Print the raw HID report that was sent, and what came back or timed out")
    commands = program.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("devices")
    sync = commands.add_parser("sync")
    sync.add_argument("--force", action="store_true")
    apply = commands.add_parser("apply")
    apply.add_argument("--hex")
    apply.add_argument("--effect", type=int)
    apply.add_argument("--brightness", type=int)
    apply.add_argument("--speed", type=int)
    apply.add_argument("--follow", type=lambda value: value.lower() in ("1", "true", "yes", "on"))
    music = commands.add_parser("music")
    music.add_argument("state", choices=("on", "off", "run"))
    music.add_argument("--effect", choices=("spectrum", "vu"))
    music.add_argument("--debug", action="store_true", dest="music_debug", help="With run, print each HID report as well as the levels")
    push = commands.add_parser("push", help="Turn per-key highlight sending on or off")
    push.add_argument("state", choices=("on", "off"))
    ha_token = commands.add_parser("ha-token", help="Prompt for a Home Assistant token and save it")
    ha_token.add_argument("--file", help="Token file to write. Defaults to the configured token_file or ha-token")
    commands.add_parser("ha-test", help="Push the current color once and print the HTTP status")
    imported = commands.add_parser("import-vscode")
    imported.add_argument("path", help="keybindings.json, or - for stdin")
    imported.add_argument("--id", default="vscode")
    imported.add_argument("--name", default="VS Code")
    imported.add_argument("--match-class", action="append", default=["Code", "code-oss", "Cursor"])
    return program


def main(argv=None):
    args = parser().parse_args(argv)
    set_debug(args.debug)
    backend = build(args)
    handlers = {
        "status": command_status,
        "devices": command_devices,
        "sync": command_sync,
        "apply": command_apply,
        "import-vscode": command_import_vscode,
        "music": command_music,
        "push": command_push,
        "ha-token": command_ha_token,
        "ha-test": command_ha_test,
    }
    try:
        code = handlers[args.command](backend, args)
    except (OSError, ValueError, TimeoutError, HomeAssistantError, HidError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return code or 0


if __name__ == "__main__":
    sys.exit(main())
