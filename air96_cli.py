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
from air96_profiles import import_vscode_keybindings
from air96_worker import refresh_device


def build(args):
    backend = Backend()
    if args.theme_dir:
        backend.theme_path = args.theme_dir
    return backend


def command_status(backend, _args):
    with file_lock(backend.state_dir):
        refresh_device(backend)
        print(json.dumps(backend.snapshot(), indent=2, sort_keys=True))


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
    patch = {"enabled": args.state == "on"}
    if args.effect:
        patch["effect"] = args.effect
    with file_lock(backend.state_dir):
        backend.update_settings({"music": patch})
    print(backend.message or "ok")
    if args.state == "on":
        print("Music mode is saved. The bar plugin applies it while it is running.")
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
    music.add_argument("state", choices=("on", "off"))
    music.add_argument("--effect", choices=("spectrum", "vu"))
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
