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


def command_screensaver(backend, args):
    enabled = args.state == "on"
    with file_lock(backend.state_dir):
        backend.update_settings({"screensaver": {"enabled": enabled}})
    print("Screensaver light show is on." if enabled else "Screensaver light show is off.")
    print("The bar worker switches to Breathing while org.omarchy.screensaver is running, and restores solid color when it exits.")
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
    screen = commands.add_parser("screensaver")
    screen.add_argument("state", choices=("on", "off"))
    ha_token = commands.add_parser("ha-token", help="Prompt for a Home Assistant token and save it")
    ha_token.add_argument("--file", help="Token file to write. Defaults to the configured token_file or ha-token")
    commands.add_parser("ha-test", help="Push the current color once and print the HTTP status")
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
        "screensaver": command_screensaver,
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
