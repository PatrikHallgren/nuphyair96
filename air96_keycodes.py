"""QMK keycode names for the Air96 keymap editor.

Values come from ``quantum/keycodes.h`` in the NuPhy QMK tree. NuPhy custom
codes are ``QK_KB_0`` (0x7E00) upward, in the order declared in ``ansi.h``.
``MO(n)`` is ``0x5220 | n``.
"""

import json
from pathlib import Path

QK_MOMENTARY = 0x5220
QK_KB = 0x7E00

# ansi.h enum order, starting at QK_KB_0.
NUPHY_CODES = (
    "RF_DFU",
    "LNK_USB",
    "LNK_RF",
    "LNK_BLE1",
    "LNK_BLE2",
    "LNK_BLE3",
    "MAC_TASK",
    "MAC_SEARCH",
    "MAC_VOICE",
    "MAC_CONSOLE",
    "MAC_DND",
    "MAC_PRT",
    "MAC_PRTA",
    "SIDE_VAI",
    "SIDE_VAD",
    "SIDE_MOD",
    "SIDE_HUI",
    "SIDE_SPI",
    "SIDE_SPD",
    "DEV_RESET",
    "SLEEP_MODE",
    "BAT_SHOW",
    "RGB_TEST",
    "BAT_NUM",
)

SHORT = {
    "KC_TRANSPARENT": "▽",
    "KC_NO": "—",
    "KC_ESC": "Esc",
    "KC_ENTER": "Enter",
    "KC_SPACE": "Space",
    "KC_BACKSPACE": "Bksp",
    "KC_TAB": "Tab",
    "KC_CAPS": "Caps",
    "KC_LEFT_SHIFT": "Shift",
    "KC_RIGHT_SHIFT": "Shift",
    "KC_LEFT_CTRL": "Ctrl",
    "KC_RIGHT_CTRL": "Ctrl",
    "KC_LEFT_ALT": "Alt",
    "KC_RIGHT_ALT": "Alt",
    "KC_LEFT_GUI": "GUI",
    "KC_RIGHT_GUI": "GUI",
    "KC_GRAVE": "`",
    "KC_MINUS": "-",
    "KC_EQUAL": "=",
    "KC_LEFT_BRACKET": "[",
    "KC_RIGHT_BRACKET": "]",
    "KC_BACKSLASH": "\\",
    "KC_SEMICOLON": ";",
    "KC_QUOTE": "'",
    "KC_COMMA": ",",
    "KC_DOT": ".",
    "KC_SLASH": "/",
    "KC_LEFT": "←",
    "KC_RIGHT": "→",
    "KC_UP": "↑",
    "KC_DOWN": "↓",
    "KC_PRINT_SCREEN": "PrtSc",
    "KC_DELETE": "Del",
    "KC_INSERT": "Ins",
    "KC_PAGE_UP": "PgUp",
    "KC_PAGE_DOWN": "PgDn",
    "KC_NUM_LOCK": "Num",
    "KC_KP_SLASH": "/",
    "KC_KP_ASTERISK": "*",
    "KC_KP_MINUS": "-",
    "KC_KP_PLUS": "+",
    "KC_KP_ENTER": "Enter",
    "KC_KP_DOT": ".",
    "RM_NEXT": "RGB+",
    "RM_HUEU": "Hue+",
    "RM_VALU": "Bri+",
    "RM_VALD": "Bri-",
    "RM_SPDU": "Spd+",
    "RM_SPDD": "Spd-",
}


def _load():
    path = Path(__file__).resolve().parent / "data" / "keycodes.json"
    raw = json.loads(path.read_text())
    by_name = {name: int(value) for name, value in raw.items()}
    for index, name in enumerate(NUPHY_CODES):
        by_name[name] = QK_KB + index
    by_value = {}
    for name, value in by_name.items():
        by_value.setdefault(value, []).append(name)
    for names in by_value.values():
        names.sort(key=lambda name: (len(name), name))
    return by_name, by_value


BY_NAME, BY_VALUE = _load()


def keycode_name(value):
    value = int(value)
    if QK_MOMENTARY <= value <= QK_MOMENTARY + 0x1F:
        return f"MO({value & 0x1F})"
    if QK_KB <= value < QK_KB + len(NUPHY_CODES):
        return NUPHY_CODES[value - QK_KB]
    names = BY_VALUE.get(value)
    if names:
        return names[0]
    return f"0x{value:04X}"


def keycode_short(value):
    value = int(value)
    if QK_MOMENTARY <= value <= QK_MOMENTARY + 0x1F:
        return f"Fn{value & 0x1F}"
    name = keycode_name(value)
    if name in SHORT:
        return SHORT[name]
    if name in NUPHY_CODES:
        return name.replace("_", " ")
    if name.startswith("KC_") and len(name) == 4:
        return name[-1]
    if name.startswith("KC_F") and name[4:].isdigit():
        return name[3:]
    if name.startswith("KC_KP_"):
        return name[6:]
    if name.startswith("0x"):
        return name
    return name.replace("KC_", "").replace("_", " ")[:8]


def keycode_value(name):
    if not isinstance(name, str):
        raise ValueError("Keycode name must be text")
    text = name.strip()
    upper = text.upper()
    if upper in BY_NAME:
        return BY_NAME[upper]
    if upper.startswith("MO(") and upper.endswith(")"):
        layer = int(upper[3:-1])
        if not 0 <= layer <= 31:
            raise ValueError("Momentary layer out of range")
        return QK_MOMENTARY | layer
    if upper.startswith("0X"):
        value = int(upper, 16)
        if not 0 <= value <= 0xFFFF:
            raise ValueError("Keycode out of range")
        return value
    raise ValueError(f"Unknown keycode {text}")


def catalog():
    """Searchable assignments for the keymap picker. One entry per value."""
    groups = {
        "Letters": lambda name: len(name) == 4 and name.startswith("KC_") and name[-1].isalpha() and name[3:].isalpha(),
        "Numbers": lambda name: name in {f"KC_{n}" for n in "0123456789"} or name in ("KC_MINUS", "KC_EQUAL", "KC_GRAVE"),
        "Modifiers": lambda name: name in {
            "KC_LEFT_SHIFT", "KC_RIGHT_SHIFT", "KC_LEFT_CTRL", "KC_RIGHT_CTRL",
            "KC_LEFT_ALT", "KC_RIGHT_ALT", "KC_LEFT_GUI", "KC_RIGHT_GUI",
        },
        "Navigation": lambda name: name in {
            "KC_ESC", "KC_ENTER", "KC_SPACE", "KC_BACKSPACE", "KC_TAB", "KC_CAPS",
            "KC_DELETE", "KC_INSERT", "KC_HOME", "KC_END", "KC_PAGE_UP", "KC_PAGE_DOWN",
            "KC_LEFT", "KC_RIGHT", "KC_UP", "KC_DOWN", "KC_PRINT_SCREEN",
        },
        "Numpad": lambda name: name.startswith("KC_KP_") or name == "KC_NUM_LOCK",
        "Media": lambda name: name in {
            "KC_MUTE", "KC_VOLU", "KC_VOLD", "KC_MPLY", "KC_MNXT", "KC_MPRV", "KC_BRID", "KC_BRIU",
        },
        "Lighting": lambda name: name.startswith("RM_") or name.startswith("SIDE_"),
        "NuPhy": lambda name: name in NUPHY_CODES and not name.startswith("SIDE_"),
    }
    entries = []
    seen = set()
    for group, predicate in groups.items():
        for name, value in sorted(BY_NAME.items()):
            if value in seen or not predicate(name):
                continue
            seen.add(value)
            entries.append({"value": value, "name": name, "group": group, "short": keycode_short(value)})
    for layer in range(8):
        value = QK_MOMENTARY | layer
        entries.append({"value": value, "name": f"MO({layer})", "group": "Layers", "short": f"Fn{layer}"})
    entries.append({"value": 0, "name": "KC_NO", "group": "Special", "short": "—"})
    entries.append({"value": 1, "name": "KC_TRANSPARENT", "group": "Special", "short": "▽"})
    return entries
