"""Detect the Omarchy screensaver and name the keyboard effect it uses.

Omarchy starts the screensaver with ``omarchy-launch-screensaver``. The
window class and the long-running process are ``org.omarchy.screensaver``
and ``omarchy-screensaver``. Breathing is a built-in RGB matrix effect, so
the show stays on the current color without a per-key overlay.
"""

import os
from pathlib import Path

# EFFECTS index: Breathing. It keeps the hue already sent over VIA.
BREATHING_EFFECT = 4


def command_is_screensaver(command):
    text = command.replace("\x00", " ")
    if "air96_" in text:
        return False
    return (
        "org.omarchy.screensaver" in text
        or "omarchy-screensaver" in text
        or "omarchy-launch-screensaver" in text
    )


def screensaver_running(root="/proc"):
    """True while an Omarchy screensaver process is in the process list."""
    base = Path(root)
    if not base.is_dir():
        return False
    for entry in base.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if command_is_screensaver(raw.decode("utf-8", "replace")):
            return True
    return False
