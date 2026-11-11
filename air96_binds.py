"""Hyprland bind parsing and keybind highlight selection.

``hyprctl binds -j`` reports ``modmask`` using Hyprland's modifier bits
(``HL_MODIFIER_META`` is bit 6, value 64). A SUPER+SHIFT bind is 65.
The idle overlay marks every non-mouse key whose bind includes SUPER.
While modifiers are held, only binds whose mask matches the held mask
(ignoring Caps Lock) stay lit.

Key names are Hyprland/XKB names (``Q``, ``Return``, ``KP_7``). ``code:N``
uses the XKB keycode, which on a PC keyboard is the evdev code plus 8.
"""

import json
import re

from air96_layout import KEYS

SUPER = 1 << 6
CAPS = 1 << 1
MOD_BITS = {
    "SHIFT": 1 << 0,
    "CAPS": CAPS,
    "CTRL": 1 << 2,
    "CONTROL": 1 << 2,
    "ALT": 1 << 3,
    "MOD1": 1 << 3,
    "MOD2": 1 << 4,
    "MOD3": 1 << 5,
    "SUPER": SUPER,
    "WIN": SUPER,
    "LOGO": SUPER,
    "MOD4": SUPER,
    "META": SUPER,
    "MOD5": 1 << 7,
}

# XKB keycodes for the letter keys on a PC keyboard (evdev + 8).
_LETTER_CODES = {}
for _index, _letter in enumerate("qwertyuiop"):
    _LETTER_CODES[24 + _index] = _letter
for _index, _letter in enumerate("asdfghjkl"):
    _LETTER_CODES[38 + _index] = _letter
for _index, _letter in enumerate("zxcvbnm"):
    _LETTER_CODES[52 + _index] = _letter

CODE_KEYS = {
    9: "esc",
    36: "enter",
    65: "space",
    22: "backspace",
    23: "tab",
    **_LETTER_CODES,
    **{10 + i: str((i + 1) % 10) for i in range(10)},
    20: "minus",
    21: "equal",
}

ALIASES = {
    "escape": "esc",
    "esc": "esc",
    "return": "enter",
    "enter": "enter",
    "kp_enter": "kp_enter",
    "space": "space",
    "backspace": "backspace",
    "bspc": "backspace",
    "tab": "tab",
    "capslock": "caps",
    "caps_lock": "caps",
    "grave": "grave",
    "asciitilde": "grave",
    "minus": "minus",
    "hyphen": "minus",
    "equal": "equal",
    "plus": "equal",
    "bracketleft": "lbracket",
    "bracketright": "rbracket",
    "backslash": "backslash",
    "semicolon": "semicolon",
    "apostrophe": "quote",
    "comma": "comma",
    "period": "dot",
    "slash": "slash",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "print": "print",
    "sys_req": "print",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "prior": "pageup",
    "page_up": "pageup",
    "next": "pagedown",
    "page_down": "pagedown",
    "num_lock": "num",
    "kp_divide": "kp_slash",
    "kp_multiply": "kp_asterisk",
    "kp_subtract": "kp_minus",
    "kp_add": "kp_plus",
    "kp_decimal": "kp_dot",
    "kp_delete": "kp_dot",
    "kp_insert": "kp0",
    "kp_end": "kp1",
    "kp_down": "kp2",
    "kp_next": "kp3",
    "kp_left": "kp4",
    "kp_begin": "kp5",
    "kp_right": "kp6",
    "kp_home": "kp7",
    "kp_up": "kp8",
    "kp_prior": "kp9",
}
for _n in range(10):
    ALIASES[str(_n)] = str(_n)
    ALIASES[f"kp_{_n}"] = f"kp{_n}"
for _name in "abcdefghijklmnopqrstuvwxyz":
    ALIASES[_name] = _name
for _n in range(1, 13):
    ALIASES[f"f{_n}"] = f"f{_n}"

KEY_IDS = {key["id"] for key in KEYS}
MODIFIER_KEYS = {
    "super_l", "super_r", "shift_l", "shift_r", "control_l", "control_r",
    "alt_l", "alt_r", "meta_l", "meta_r", "hyper_l", "hyper_r",
}

BIND_LINE = re.compile(r"^(bind[a-z]*)\s*=\s*(.*)$", re.IGNORECASE)


def effective_mask(mask):
    return int(mask) & ~CAPS


def key_to_id(name):
    if not isinstance(name, str):
        return None
    text = name.strip()
    if not text or text.lower().startswith("mouse"):
        return None
    lowered = text.lower()
    if lowered in MODIFIER_KEYS or lowered in {"super", "shift", "ctrl", "control", "alt", "meta"}:
        return None
    if lowered.startswith("code:"):
        try:
            code = int(lowered[5:])
        except ValueError:
            return None
        return CODE_KEYS.get(code)
    ident = ALIASES.get(lowered)
    if ident in KEY_IDS:
        return ident
    return None


def parse_mod_string(text):
    mask = 0
    for part in re.split(r"[\s+]+", text.strip()):
        if not part:
            continue
        bit = MOD_BITS.get(part.upper())
        if bit is None:
            raise ValueError(f"Unknown modifier {part}")
        mask |= bit
    return mask


def _bind(key, modmask, submap, label, dispatcher="", arg=""):
    ident = key_to_id(key)
    if ident is None:
        return None
    return {
        "key": ident,
        "modmask": int(modmask) & 0xFF,
        "submap": submap or "",
        "label": (label or f"{dispatcher} {arg}").strip()[:160],
        "dispatcher": str(dispatcher or "")[:80],
        "arg": str(arg or "")[:160],
    }


def parse_hyprctl_binds(items):
    if isinstance(items, str):
        items = json.loads(items)
    if not isinstance(items, list):
        raise ValueError("hyprctl binds JSON must be a list")
    binds = []
    for item in items:
        if not isinstance(item, dict) or item.get("mouse") or item.get("catch_all"):
            continue
        bind = _bind(
            str(item.get("key") or ""),
            item.get("modmask") or 0,
            str(item.get("submap") or ""),
            str(item.get("description") or ""),
            item.get("dispatcher") or "",
            item.get("arg") or "",
        )
        if bind:
            binds.append(bind)
    return binds


def parse_bind_lines(text):
    binds = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        match = BIND_LINE.match(line)
        if not match:
            continue
        kind = match.group(1).lower()
        parts = [part.strip() for part in match.group(2).split(",")]
        if len(parts) < 3:
            continue
        try:
            mask = parse_mod_string(parts[0])
        except ValueError:
            continue
        if kind == "bindd" and len(parts) >= 4:
            label, dispatcher, arg = parts[2], parts[3], ",".join(parts[4:])
        else:
            label, dispatcher, arg = "", parts[2], ",".join(parts[3:])
        bind = _bind(parts[1], mask, "", label, dispatcher, arg)
        if bind:
            binds.append(bind)
    return binds


def compose_highlights(binds, held=0, submap="", profile=None, color="#ffffff"):
    """Pick diagram keys to light.

    ``held`` 0: dim keys whose bind is exactly SUPER, not every bind that
    merely includes SUPER. Super+Shift stays dark until Shift is held.
    ``held`` nonzero: bright only the keys that complete that exact mask.
    Profile keys are hints for the focused app. An active Hyprland bind on
    the same key wins, because that bind is what the compositor will run.
    """
    held_mask = effective_mask(held)
    current = submap or ""
    chosen = {}
    for bind in binds:
        if (bind.get("submap") or "") != current:
            continue
        mask = effective_mask(bind.get("modmask") or 0)
        if held_mask == 0:
            if mask != SUPER:
                continue
            level = "idle"
        elif mask == held_mask and mask != 0:
            level = "active"
        else:
            continue
        chosen[bind["key"]] = {
            "level": level,
            "label": bind.get("label") or "",
            "color": color or "#ffffff",
            "source": "bind",
        }
    if profile and held_mask == 0:
        for entry in profile.get("keys") or []:
            ident = entry.get("key")
            if ident not in KEY_IDS:
                continue
            existing = chosen.get(ident)
            if existing:
                continue
            mods = entry.get("mods") or []
            label = entry.get("label") or profile.get("name") or ""
            if mods:
                label = "+".join(mods) + " " + label
            chosen[ident] = {
                "level": "profile",
                "label": label.strip(),
                "color": entry.get("color") or "#e0af68",
                "source": "profile",
            }
    return chosen


def held_names(mask):
    names = []
    for name, bit in (("shift", 1), ("ctrl", 4), ("alt", 8), ("super", SUPER)):
        if effective_mask(mask) & bit:
            names.append(name)
    return names
