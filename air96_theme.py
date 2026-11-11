"""Read the active Omarchy theme color.

Omarchy keeps the running theme at ``~/.local/state/omarchy/current/theme``.
``keyboard.rgb`` wins when it is present. Themes ship that file either as
``#RRGGBB`` (the ``{{ accent }}`` template) or as bare ``RRGGBB`` (Tokyo Night
ships ``ff00ff``). Otherwise the accent line in ``colors.toml`` is used.
"""

import os
from pathlib import Path
import re

from air96_protocol import normalize_hex

THEME_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "omarchy" / "current" / "theme"
ASSIGNMENT = re.compile(
    r"""^([A-Za-z0-9_]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s#]+))"""
)


def theme_dir(path=None):
    return Path(path) if path else THEME_DIR


def parse_colors_toml(text):
    colors = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT.match(stripped)
        if not match:
            continue
        raw = match.group(2) if match.group(2) is not None else match.group(3) if match.group(3) is not None else match.group(4)
        colors[match.group(1)] = raw.strip()
    return colors


def color_from_keyboard_file(text):
    for line in text.splitlines():
        color = normalize_hex(line.strip())
        if color:
            return color
    return ""


def color_from_theme_text(keyboard_rgb="", colors_toml=""):
    from_keyboard = color_from_keyboard_file(keyboard_rgb) if keyboard_rgb else ""
    if from_keyboard:
        return from_keyboard
    accent = parse_colors_toml(colors_toml).get("accent", "") if colors_toml else ""
    return normalize_hex(accent)


def read_theme_color(path=None, limit=8192):
    directory = theme_dir(path)
    keyboard = _read(directory / "keyboard.rgb", limit)
    colors = _read(directory / "colors.toml", limit)
    return color_from_theme_text(keyboard, colors)


def _read(path, limit):
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > limit:
        return ""
    return data.decode("utf-8", errors="replace")
