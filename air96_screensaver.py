"""Detect the Omarchy screensaver and name the keyboard effect it uses.

Omarchy starts the screensaver with ``omarchy-launch-screensaver``. The
window class and the long-running process are ``org.omarchy.screensaver``
and ``omarchy-screensaver``. Breathing is RGB matrix effect 5 on the flashed
Omarchy keymap (Alphas Mods occupies index 2, so the old index 4 is the
left/right gradient). The show is not written to EEPROM.
"""

import os
from pathlib import Path

# RGB_MATRIX_BREATHING on nuphy/air96_v2 with alphas_mods enabled.
BREATHING_EFFECT = 5
# Firmware default in keyboard.json. Zero speed freezes the sine.
SHOW_SPEED = 153


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
