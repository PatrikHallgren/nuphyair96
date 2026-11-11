"""Per-app keybind profiles.

A profile matches the focused Hyprland window. Class comparison is
case-insensitive and exact (``hyprctl activewindow`` prints the class).
``title_contains`` is optional and ANDed with the class match.

Shipped examples live next to the plugin. Files in the user profile
directory override the same ``id``. Nothing here talks to the keyboard.
"""

import json
from pathlib import Path

from air96_layout import KEYS
from air96_protocol import normalize_hex

KEY_IDS = {key["id"] for key in KEYS}
MODS = {"ctrl", "shift", "alt", "super"}
PLUGIN_PROFILES = Path(__file__).resolve().parent / "profiles"


class ProfileError(ValueError):
    pass


def _strings(value, field):
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ProfileError(f"{field} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def validate_profile(raw):
    if not isinstance(raw, dict):
        raise ProfileError("Profile must be an object")
    ident = raw.get("id")
    if not isinstance(ident, str) or not ident.strip() or len(ident) > 80:
        raise ProfileError("Profile id is missing")
    match = raw.get("match") or {}
    if not isinstance(match, dict):
        raise ProfileError("Profile match must be an object")
    classes = _strings(match.get("class"), "match.class")
    titles = _strings(match.get("title_contains"), "match.title_contains")
    keys = raw.get("keys")
    if not isinstance(keys, list):
        raise ProfileError("Profile keys must be a list")
    cleaned_keys = []
    for entry in keys:
        if not isinstance(entry, dict):
            raise ProfileError("Profile key must be an object")
        key = entry.get("key")
        if key not in KEY_IDS:
            raise ProfileError(f"Unknown key {key}")
        mods = [mod.lower() for mod in _strings(entry.get("mods"), "mods")]
        if any(mod not in MODS for mod in mods):
            raise ProfileError("Profile mods must be ctrl, shift, alt, or super")
        color = entry.get("color") or "#e0af68"
        if not normalize_hex(color):
            raise ProfileError("Profile color must be #RRGGBB")
        cleaned_keys.append({
            "key": key,
            "mods": mods,
            "label": str(entry.get("label") or "")[:120],
            "color": normalize_hex(color),
        })
    enabled = raw.get("enabled", True)
    if type(enabled) is not bool:
        raise ProfileError("Profile enabled must be true or false")
    return {
        "id": ident.strip(),
        "name": str(raw.get("name") or ident).strip()[:80],
        "enabled": enabled,
        "match": {"class": classes, "title_contains": titles},
        "keys": cleaned_keys,
    }


def load_profile_text(text):
    return validate_profile(json.loads(text))


def load_directory(path):
    directory = Path(path)
    profiles = {}
    if not directory.is_dir():
        return profiles
    for file in sorted(directory.glob("*.json")):
        try:
            profile = load_profile_text(file.read_text())
        except (OSError, json.JSONDecodeError, ProfileError) as exc:
            raise ProfileError(f"{file.name}: {exc}") from exc
        profiles[profile["id"]] = profile
    return profiles


def load_profiles(user_dir=None, shipped_dir=None):
    merged = load_directory(shipped_dir or PLUGIN_PROFILES)
    if user_dir:
        merged.update(load_directory(user_dir))
    return [profile for profile in merged.values() if profile["enabled"]]


def match_profile(profiles, window_class, title=""):
    current = (window_class or "").casefold()
    current_title = title or ""
    for profile in profiles:
        classes = [name.casefold() for name in profile["match"]["class"]]
        titles = profile["match"]["title_contains"]
        class_ok = not classes or current in classes
        title_ok = not titles or any(part.casefold() in current_title.casefold() for part in titles)
        if classes or titles:
            if class_ok and title_ok and (current or current_title):
                return profile
    return None


def import_vscode_keybindings(text, *, profile_id, name, classes):
    """Turn a VS Code ``keybindings.json`` into a profile.

    Only the first chord of each binding is kept. Commands that start with
    ``-`` are unbinds and are skipped. Keys that are not on the Air96 are
    skipped rather than failing the import.
    """
    from air96_binds import key_to_id

    data = json.loads(text)
    if not isinstance(data, list):
        raise ProfileError("VS Code keybindings must be a list")
    mod_map = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt",
               "cmd": "super", "meta": "super", "win": "super"}
    keys = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "")
        if not command or command.startswith("-"):
            continue
        chord = str(item.get("key") or "").split(" ")[0]
        if not chord:
            continue
        mods = []
        key_name = ""
        for part in chord.split("+"):
            lowered = part.strip().casefold()
            if lowered in mod_map:
                mods.append(mod_map[lowered])
            else:
                key_name = part.strip()
        ident = key_to_id(key_name)
        if not ident or ident in seen:
            continue
        seen.add(ident)
        label = command.rsplit(".", 1)[-1].replace("_", " ")
        keys.append({"key": ident, "mods": mods, "label": label[:120], "color": "#89b4fa"})
    if not keys:
        raise ProfileError("No Air96 keys found in those keybindings")
    return validate_profile({
        "id": profile_id,
        "name": name,
        "match": {"class": list(classes), "title_contains": []},
        "keys": keys,
    })
