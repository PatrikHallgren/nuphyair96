"""Lighting, keymap, theme, and Home Assistant orchestration.

HID access stays behind the transport object. Tests pass a fake transport and
never open ``/dev/hidraw``.
"""

import contextlib
import fcntl
import json
import os
from pathlib import Path
import time

from air96_ha import (
    HomeAssistantError,
    light_is_on,
    normalize_entities,
    normalize_url,
    resolve_token,
    send as send_ha,
    service_request,
    state_request,
    turn_on_payload,
)
from air96_keycodes import catalog, keycode_name, keycode_short
from air96_layout import KEYS, LAYER_COUNT, LAYERS, LED_COUNT, MATRIX_COLS, MATRIX_ROWS
from air96_profiles import ProfileError, load_profiles, match_profile
from air96_protocol import (
    BUFFER_CHUNK,
    CMD_PER_KEY_CLEAR,
    CMD_UNHANDLED,
    EFFECTS,
    SOLID_EFFECT,
    VAL_BRIGHTNESS,
    VAL_COLOR,
    VAL_EFFECT,
    VAL_SPEED,
    ProtocolError,
    buffer_request,
    effect_name,
    get_keycode_request,
    hex_to_qmk_hs,
    keymap_offset,
    keymap_size,
    layer_count_request,
    lighting_get,
    lighting_save,
    lighting_set,
    normalize_hex,
    parse_buffer,
    parse_keycode,
    parse_layer_count,
    parse_lighting_get,
    parse_protocol_version,
    per_key_capabilities,
    per_key_clear_request,
    per_key_delta_packets,
    per_key_mods_request,
    per_key_probe_request,
    per_key_set_packets,
    parse_per_key_mods,
    per_key_supported,
    protocol_version_request,
    set_keycode_request,
)
from air96_hid import HidError
from air96_theme import read_theme_color
from air96_binds import compose_highlights, held_names

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "omarchy-nuphy-air96"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "omarchy-nuphy-air96"

VERIFICATION = {
    "lighting": "VIA RGB-matrix channel implemented; not run on an Air96",
    "keymap": "VIA dynamic keymap implemented; not run on an Air96",
    "perKey": "On-screen highlights work on stock firmware. A successful 0xA6 probe means this keyboard can take per-key colors.",
    "theme": "keyboard.rgb and colors.toml parsing is tested. Live theme switching was not run here.",
    "homeAssistant": "Light payloads are tested. No Home Assistant server was called.",
    "modifiers": "The firmware reports the modifier mask. The evdev listener is optional and is not required for Super highlights.",
}


def verification_notes(per_key):
    notes = dict(VERIFICATION)
    if per_key is True:
        notes["perKey"] = (
            "This keyboard answered the per-key probe. The bar worker sends colors when push is on. "
            "The static sentence about the firmware not being flashed was a development note, not a live check."
        )
    elif per_key is False:
        notes["perKey"] = "The per-key probe was not accepted. Stock firmware leaves the matrix effect alone."
    return notes


def default_config():
    return {
        "lighting": {
            "effect": SOLID_EFFECT,
            "brightness": 180,
            "speed": 128,
            "hex": "#ffffff",
            "follow_theme": False,
            "solid_when_following": True,
        },
        "home_assistant": {
            "enabled": False,
            "url": "",
            "token_env": "HA_TOKEN",
            "token_file": "",
            "token": "",
            "entities": [],
            "sync_brightness": False,
            "only_when_on": True,
        },
        "modifiers": {"enabled": False},
        "per_key": {"enabled": True, "push_to_keyboard": True},
        "profiles": {"enabled": True},
        "music": {"enabled": False, "effect": "spectrum"},
    }


def _bool(value, field):
    if type(value) is not bool:
        raise ValueError(f"{field} must be true or false")
    return value


def _byte(value, field):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError(f"{field} must be an integer from 0 to 255")
    return value


def validate_config(raw):
    if not isinstance(raw, dict):
        raise ValueError("Config must be an object")
    base = default_config()
    unknown = set(raw) - set(base)
    if unknown:
        raise ValueError("Unknown config section: " + ", ".join(sorted(unknown)))
    config = default_config()
    if "lighting" in raw:
        section = raw["lighting"]
        if not isinstance(section, dict):
            raise ValueError("lighting must be an object")
        extra = set(section) - set(base["lighting"])
        if extra:
            raise ValueError("Unknown lighting option: " + ", ".join(sorted(extra)))
        merged = {**base["lighting"], **section}
        merged["effect"] = _byte(merged["effect"], "effect")
        merged["brightness"] = _byte(merged["brightness"], "brightness")
        merged["speed"] = _byte(merged["speed"], "speed")
        color = normalize_hex(merged["hex"])
        if not color:
            raise ValueError("Color must be #RRGGBB")
        merged["hex"] = color
        merged["follow_theme"] = _bool(merged["follow_theme"], "follow_theme")
        merged["solid_when_following"] = _bool(merged["solid_when_following"], "solid_when_following")
        config["lighting"] = merged
    if "home_assistant" in raw:
        section = raw["home_assistant"]
        if not isinstance(section, dict):
            raise ValueError("home_assistant must be an object")
        extra = set(section) - set(base["home_assistant"])
        if extra:
            raise ValueError("Unknown Home Assistant option: " + ", ".join(sorted(extra)))
        merged = {**base["home_assistant"], **section}
        merged["enabled"] = _bool(merged["enabled"], "home_assistant.enabled")
        merged["url"] = str(merged["url"] or "").strip()
        if merged["url"]:
            merged["url"] = normalize_url(merged["url"])
        merged["token_env"] = str(merged["token_env"] or "HA_TOKEN").strip()[:80]
        merged["token_file"] = str(merged["token_file"] or "").strip()[:300]
        merged["token"] = str(merged["token"] or "").strip()
        merged["sync_brightness"] = _bool(merged["sync_brightness"], "home_assistant.sync_brightness")
        merged["only_when_on"] = _bool(merged["only_when_on"], "home_assistant.only_when_on")
        if merged["entities"]:
            merged["entities"] = normalize_entities(merged["entities"])
        else:
            merged["entities"] = []
        if merged["enabled"] and (not merged["url"] or not merged["entities"]):
            raise ValueError("Home Assistant needs a URL and at least one light entity")
        config["home_assistant"] = merged
    for name in ("modifiers", "per_key", "profiles"):
        if name not in raw:
            continue
        section = raw[name]
        if not isinstance(section, dict):
            raise ValueError(f"{name} must be an object")
        extra = set(section) - set(base[name])
        if extra:
            raise ValueError(f"Unknown {name} option: " + ", ".join(sorted(extra)))
        merged = {**base[name], **section}
        for key, value in merged.items():
            merged[key] = _bool(value, f"{name}.{key}")
        config[name] = merged
    if "music" in raw:
        section = raw["music"]
        if not isinstance(section, dict):
            raise ValueError("music must be an object")
        extra = set(section) - set(base["music"])
        if extra:
            raise ValueError("Unknown music option: " + ", ".join(sorted(extra)))
        merged = {**base["music"], **section}
        merged["enabled"] = _bool(merged["enabled"], "music.enabled")
        if merged["effect"] not in ("spectrum", "vu"):
            raise ValueError("music.effect must be spectrum or vu")
        config["music"] = merged
    return config


def load_config(path):
    if not path.exists():
        return default_config()
    try:
        return validate_config(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Config could not be loaded: {exc}") from exc


def save_config(path, config):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(config, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(encoded)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


@contextlib.contextmanager
def file_lock(directory, timeout=2):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "lock").open("w") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Air96 settings are busy")
                time.sleep(0.02)
        yield


class Backend:
    def __init__(self, config_path=None, state_dir=None, theme_path=None, profiles_dir=None, environ=None):
        self.config_path = Path(config_path) if config_path else CONFIG_DIR / "config.json"
        self.state_dir = Path(state_dir) if state_dir else STATE_DIR
        self.theme_path = theme_path
        self.profiles_dir = Path(profiles_dir) if profiles_dir else self.config_path.parent / "profiles"
        self.environ = environ if environ is not None else os.environ
        self.transport = None
        self.device = None
        self.setup_issue = "not-found"
        self.config = default_config()
        self.config_error = ""
        self.error = ""
        self.message = ""
        self.applied_signature = ""
        self.device_identity = ""
        self.per_key = None
        self.per_key_reason = "Per-key lighting has not been probed."
        self.hardware = None
        self.keymap = None
        self.keymap_backup = ""
        self.conflicts = []
        self.binds = []
        self.held = 0
        self.modifier_permission = ""
        self.window_class = ""
        self.window_title = ""
        self.submap = ""
        self.ha_error = ""
        self.ha_pushed = ""
        self.music_error = ""
        self.per_key_caps = None
        self.frame_kind = ""
        self._music_frame = None
        self.last_direct = 0.0
        self._config_mtime = 0
        self._load()

    def _load(self):
        try:
            self.config = load_config(self.config_path)
            self.config_error = ""
            self._config_mtime = self.config_path.stat().st_mtime if self.config_path.exists() else 0
        except ValueError as exc:
            self.config = default_config()
            self.config_error = str(exc)[:400]

    def reload_config(self):
        self._load()

    def reload_if_external(self):
        """Pick up a config written by the CLI. In-process saves update the mtime stamp."""
        if not self.config_path.exists():
            return False
        mtime = self.config_path.stat().st_mtime
        if mtime == self._config_mtime:
            return False
        self._load()
        return True

    def _save(self):
        save_config(self.config_path, self.config)
        try:
            self._config_mtime = self.config_path.stat().st_mtime
        except OSError:
            self._config_mtime = 0

    def set_device(self, device, transport, setup_issue):
        identity = ""
        if device:
            identity = f"{device['vid']:04x}:{device['pid']:04x}:{device['path']}"
        if identity != self.device_identity:
            self.applied_signature = ""
            self.per_key = None
            self.per_key_caps = None
            self.per_key_reason = "Per-key lighting has not been probed."
            self.frame_kind = ""
            self.last_direct = 0.0
            self.hardware = None
            self.keymap = None
            self.conflicts = []
        self.device = device
        self.transport = transport
        self.device_identity = identity
        self.setup_issue = setup_issue
        if transport and self.per_key is None:
            self._probe()

    def _transact(self, payload):
        if not self.transport:
            raise ProtocolError("Air96 is not connected over USB")
        response = self.transport.transact(payload)
        if not response or response[0] == CMD_UNHANDLED:
            raise ProtocolError("Keyboard returned VIA unhandled for this command")
        return response

    def _probe(self):
        try:
            version = parse_protocol_version(self._transact(protocol_version_request()))
        except (ProtocolError, OSError, TimeoutError) as exc:
            self.setup_issue = "via-failed"
            self.error = str(exc)[:400]
            self.transport = None
            return
        if version < 0x0009:
            self.error = f"Unexpected VIA protocol version {version:#06x}"
        try:
            response = self.transport.transact(per_key_probe_request())
        except (OSError, TimeoutError) as exc:
            self.per_key = False
            self.per_key_reason = str(exc)[:300]
            return
        self.per_key = per_key_supported(response)
        self.per_key_caps = per_key_capabilities(response)
        if self.per_key:
            leds = self.per_key_caps.get("leds") if self.per_key_caps else None
            self.per_key_reason = "Custom firmware accepted per-key colors (%s LEDs)." % (leds or 100)
        else:
            self.per_key_reason = (
                "Stock VIA firmware has no per-key command (probe returned unhandled). "
                "The on-screen map still highlights keys. See docs/PER-KEY.md to add the command in QMK."
            )
        try:
            self.hardware = self._read_lighting()
        except (ProtocolError, OSError, TimeoutError) as exc:
            self.error = str(exc)[:400]

    def _read_lighting(self):
        effect = parse_lighting_get(self._transact(lighting_get(VAL_EFFECT)), VAL_EFFECT)
        brightness = parse_lighting_get(self._transact(lighting_get(VAL_BRIGHTNESS)), VAL_BRIGHTNESS)
        speed = parse_lighting_get(self._transact(lighting_get(VAL_SPEED)), VAL_SPEED)
        hue, sat = parse_lighting_get(self._transact(lighting_get(VAL_COLOR)), VAL_COLOR)
        return {"effect": effect, "effectName": effect_name(effect), "brightness": brightness,
                "speed": speed, "hue": hue, "sat": sat}

    def theme_color(self):
        return read_theme_color(self.theme_path)

    def _target(self, lighting):
        if lighting["follow_theme"]:
            color = self.theme_color()
            if not color:
                raise ValueError("Theme keyboard.rgb and colors.toml accent are missing or not a hex color")
            effect = SOLID_EFFECT if lighting["solid_when_following"] else lighting["effect"]
            return effect, color
        return lighting["effect"], lighting["hex"]

    def apply_lighting(self, patch=None, force=False, push_ha=True):
        if patch is not None:
            self.config = validate_config({**self.config, "lighting": {**self.config["lighting"], **patch}})
            self._save()
        lighting = self.config["lighting"]
        effect, color = self._target(lighting)
        signature = json.dumps([self.device_identity, effect, lighting["brightness"], lighting["speed"], color])
        if not force and signature == self.applied_signature:
            self.message = "Lighting already matches this theme"
            return
        hue, sat = hex_to_qmk_hs(color)
        self._transact(lighting_set(VAL_EFFECT, effect))
        self._transact(lighting_set(VAL_BRIGHTNESS, lighting["brightness"]))
        self._transact(lighting_set(VAL_SPEED, lighting["speed"]))
        self._transact(lighting_set(VAL_COLOR, hue, sat))
        self._transact(lighting_save())
        self.applied_signature = signature
        self.hardware = {"effect": effect, "effectName": effect_name(effect), "brightness": lighting["brightness"],
                         "speed": lighting["speed"], "hue": hue, "sat": sat}
        self.message = f"Backlight set to {color} ({effect_name(effect)})"
        self.error = ""
        if push_ha and self.config["home_assistant"]["enabled"]:
            try:
                self.push_home_assistant(color)
            except HomeAssistantError:
                # The keyboard changed. Drop the signature so the next sync retries the lights.
                self.applied_signature = ""
                raise
        if self.config["per_key"]["push_to_keyboard"] and self.per_key and not self.config["music"]["enabled"]:
            self.push_per_key()

    def sync(self, force=False):
        if not self.config["lighting"]["follow_theme"]:
            self.message = "Theme follow is off"
            return
        self.apply_lighting(force=force)

    def update_settings(self, patch):
        if not isinstance(patch, dict):
            raise ValueError("Settings must be an object")
        merged = json.loads(json.dumps(self.config))
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        self.config = validate_config(merged)
        self._save()
        self.message = "Settings saved"
        self.config_error = ""

    def push_home_assistant(self, color=None, brightness=None):
        section = self.config["home_assistant"]
        color = color or (self.theme_color() if self.config["lighting"]["follow_theme"] else self.config["lighting"]["hex"])
        token = resolve_token(self.environ, section["token_env"], section["token_file"], section["token"])
        entities = normalize_entities(section["entities"])
        skipped = []
        if section["only_when_on"]:
            lit = []
            for entity in entities:
                prepared = state_request(section["url"], token, entity)
                try:
                    result = send_ha(prepared)
                    on = light_is_on(result["body"])
                except HomeAssistantError as exc:
                    self.ha_error = str(exc)[:400]
                    raise
                if on:
                    lit.append(entity)
                else:
                    skipped.append(entity)
            entities = lit
            if not entities:
                self.ha_error = ""
                self.message = "Home Assistant lights are off; color not pushed"
                return {"status": None, "skipped": True, "body": "", "leftOff": skipped}
        level = None
        if section["sync_brightness"]:
            level = self.config["lighting"]["brightness"] if brightness is None else brightness
        payload = turn_on_payload(entities, color, level)
        prepared = service_request(section["url"], token, payload)
        try:
            result = send_ha(prepared)
        except HomeAssistantError as exc:
            self.ha_error = str(exc)[:400]
            raise
        self.ha_error = ""
        self.ha_pushed = color
        if skipped:
            self.message = f"Home Assistant lights set to {color}; left off: {', '.join(skipped)}"
        else:
            self.message = f"Home Assistant lights set to {color}"
        result = dict(result)
        result["skipped"] = False
        result["leftOff"] = skipped
        return result

    def load_keymap(self):
        layers = parse_layer_count(self._transact(layer_count_request()))
        size = keymap_size(layers, MATRIX_ROWS, MATRIX_COLS)
        blob = bytearray()
        offset = 0
        while offset < size:
            chunk = min(BUFFER_CHUNK, size - offset)
            blob += parse_buffer(self._transact(buffer_request(offset, chunk)), offset, chunk)
            offset += chunk
        keys = {}
        for layer in range(layers):
            for row in range(MATRIX_ROWS):
                for col in range(MATRIX_COLS):
                    start = keymap_offset(layer, row, col, MATRIX_ROWS, MATRIX_COLS)
                    value = (blob[start] << 8) | blob[start + 1]
                    physical = any(key["row"] == row and key["col"] == col for key in KEYS)
                    if not physical:
                        continue
                    keys[f"{layer}:{row}:{col}"] = {
                        "layer": layer, "row": row, "col": col, "value": value,
                        "name": keycode_name(value), "short": keycode_short(value),
                    }
        self.keymap = {"layers": layers, "keys": keys}
        self.conflicts = []
        self.message = "Keymap read from the keyboard"
        self.error = ""
        return self.keymap

    def apply_keymap(self, changes):
        if not self.keymap:
            raise ValueError("Read the keymap before applying edits")
        if not isinstance(changes, list) or not changes:
            raise ValueError("No keymap changes to apply")
        cleaned = []
        seen = set()
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Invalid keymap change")
            layer = change.get("layer")
            row = change.get("row")
            col = change.get("col")
            value = change.get("value")
            original = change.get("original")
            for number, field, limit in ((layer, "layer", 31), (row, "row", MATRIX_ROWS - 1), (col, "col", MATRIX_COLS - 1)):
                if type(number) is not int or not 0 <= number <= limit:
                    raise ValueError(f"Invalid keymap {field}")
            if type(value) is not int or type(original) is not int or not 0 <= value <= 0xFFFF or not 0 <= original <= 0xFFFF:
                raise ValueError("Invalid keycode")
            address = f"{layer}:{row}:{col}"
            if address in seen or address not in self.keymap["keys"]:
                raise ValueError("Keymap change is not on a physical key")
            seen.add(address)
            cleaned.append({"layer": layer, "row": row, "col": col, "value": value, "original": original})
        conflicts = []
        current = {}
        for change in cleaned:
            value = parse_keycode(self._transact(get_keycode_request(change["layer"], change["row"], change["col"])),
                                  change["layer"], change["row"], change["col"])
            current[(change["layer"], change["row"], change["col"])] = value
            if value not in (change["original"], change["value"]):
                conflicts.append({**change, "current": value, "currentName": keycode_name(value)})
        self.conflicts = conflicts
        if conflicts:
            self.error = "Assignments changed on the keyboard; nothing was written"
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        backup = self.state_dir / "keymap-backups"
        backup.mkdir(mode=0o700, exist_ok=True)
        path = backup / f"keymap-{time.time_ns()}.json"
        path.write_text(json.dumps(self.keymap["keys"], sort_keys=True))
        os.chmod(path, 0o600)
        self.keymap_backup = str(path)
        for change in cleaned:
            if current[(change["layer"], change["row"], change["col"])] == change["value"]:
                continue
            response = self._transact(set_keycode_request(change["layer"], change["row"], change["col"], change["value"]))
            if response[0] != 0x05:
                raise ProtocolError("Keymap write was not acknowledged")
        self.load_keymap()
        mismatched = [
            change for change in cleaned
            if self.keymap["keys"][f"{change['layer']}:{change['row']}:{change['col']}"]["value"] != change["value"]
        ]
        if mismatched:
            self.error = "Readback differs from the requested assignments"
            self.message = ""
            return
        self.message = "Keymap applied"
        self.error = ""

    def active_profile(self):
        if not self.config["profiles"]["enabled"]:
            return None
        try:
            profiles = load_profiles(self.profiles_dir)
        except ProfileError as exc:
            self.error = str(exc)[:400]
            return None
        return match_profile(profiles, self.window_class, self.window_title)

    def highlights(self):
        if not self.config["per_key"]["enabled"]:
            return {}
        color = self.theme_color() or self.config["lighting"]["hex"]
        return compose_highlights(self.binds, self.held, self.submap, self.active_profile(), color)

    def _write_colors(self, colors):
        for payload in per_key_set_packets(colors):
            response = self._transact(payload)
            if response[0] != 0xA7:
                raise ProtocolError("Per-key write was not acknowledged")
        self.last_direct = time.monotonic()

    def read_keyboard_mods(self):
        """Hyprland modmask from this keyboard, or None on stock / older firmware.

        The keyboard already knows which modifiers are down. That is what
        makes Super+Shift light a different set from Super alone, without a
        second udev rule on /dev/input.
        """
        if not self.per_key or self.transport is None:
            return None
        try:
            response = self.transport.transact(per_key_mods_request())
        except (OSError, TimeoutError, HidError):
            return None
        return parse_per_key_mods(response)

    def push_per_key(self):
        if not self.per_key:
            raise ProtocolError(self.per_key_reason)
        mods = self.read_keyboard_mods()
        if mods is not None:
            self.held = mods
        colors = [(0, 0, 0)] * LED_COUNT
        base = self.theme_color() or self.config["lighting"]["hex"]
        red, green, blue = _scale(base, 0.04)
        for key in KEYS:
            colors[key["led"]] = (red, green, blue)
        for ident, item in self.highlights().items():
            key = next((entry for entry in KEYS if entry["id"] == ident), None)
            if key is None:
                continue
            scale = {"idle": 0.55, "active": 1.0, "profile": 0.7}.get(item["level"], 0.6)
            colors[key["led"]] = _scale(item["color"], scale)
        self._write_colors(colors)
        self.frame_kind = "highlight"
        self.message = "Per-key frame sent"

    def keepalive_overlay(self):
        """Refresh the 2 second overlay timer without rewriting LEDs or clearing."""
        if not self.per_key or self.transport is None:
            return False
        response = self._transact(per_key_probe_request())
        if response[0] != 0xA6:
            raise ProtocolError("Per-key keepalive was not acknowledged")
        self.last_direct = time.monotonic()
        return True

    def clear_per_key(self):
        if not self.per_key or self.transport is None:
            self.frame_kind = ""
            return
        response = self.transport.transact(per_key_clear_request())
        if not response or response[0] != CMD_PER_KEY_CLEAR:
            raise ProtocolError("Per-key clear was not acknowledged")
        self.frame_kind = ""
        self._music_frame = None
        self.last_direct = 0.0

    def push_music(self, levels):
        from air96_audio import frame_colors, via_pulse
        tint = self.theme_color() or self.config["lighting"]["hex"]
        if self.per_key:
            colors = frame_colors(levels, self.config["music"]["effect"], tint)
            packets = per_key_delta_packets(self._music_frame, colors)
            old_timeout = getattr(self.transport, "timeout", None)
            if old_timeout is not None:
                self.transport.timeout = min(float(old_timeout), 0.08)
            try:
                if packets:
                    for payload in packets:
                        response = self._transact(payload)
                        if response[0] != 0xA7:
                            raise ProtocolError("Per-key write was not acknowledged")
                else:
                    response = self._transact(per_key_probe_request())
                    if response[0] != 0xA6:
                        raise ProtocolError("Per-key keepalive was not acknowledged")
            finally:
                if old_timeout is not None:
                    self.transport.timeout = old_timeout
            self._music_frame = [tuple(color) for color in colors]
            self.last_direct = time.monotonic()
            self.frame_kind = "music"
            self.music_error = ""
            self.message = "Music frame sent" if packets else "Music frame held"
            return
        if self.transport is None:
            raise ProtocolError("Air96 is not connected over USB")
        pulse = via_pulse(levels, tint, self.config["lighting"]["brightness"])
        self._transact(lighting_set(VAL_EFFECT, pulse["effect"]))
        self._transact(lighting_set(VAL_BRIGHTNESS, pulse["brightness"]))
        self._transact(lighting_set(VAL_COLOR, pulse["hue"], pulse["sat"]))
        self.applied_signature = ""
        self.frame_kind = "music"
        self.music_error = ""
        self.hardware = {
            "effect": pulse["effect"], "effectName": effect_name(pulse["effect"]),
            "brightness": pulse["brightness"], "speed": self.config["lighting"]["speed"],
            "hue": pulse["hue"], "sat": pulse["sat"],
        }
        self.message = "Music pulse sent (stock firmware, not saved)"

    def release_overlay(self):
        """Leave music or a direct frame and restore the saved VIA effect."""
        if self.per_key:
            self.clear_per_key()
        self.frame_kind = ""
        if self.transport is not None:
            self.apply_lighting(force=True, push_ha=False)

    def snapshot(self, include_keymap=False):
        section = self.config["home_assistant"]
        token_set = bool(section["token"] or self.environ.get(section["token_env"]) or section["token_file"])
        lighting = dict(self.config["lighting"])
        profile = self.active_profile()
        device = self.device or {}
        body = {
            "connected": self.transport is not None,
            "keyboardName": device.get("name") or ("NuPhy Air96 V2" if device else ""),
            "path": device.get("path", ""),
            "vid": device.get("vid", 0),
            "pid": device.get("pid", 0),
            "iface": device.get("iface"),
            "setupIssue": self.setup_issue if not self.transport else "",
            "error": self.config_error or self.error,
            "message": self.message,
            "theme": self.theme_color(),
            "lighting": lighting,
            "effects": [{"id": index, "name": name} for index, name in enumerate(EFFECTS)],
            "layers": list(LAYERS),
            "layout": KEYS,
            "highlights": self.highlights(),
            "modifiers": {
                "enabled": self.config["modifiers"]["enabled"],
                "held": self.held,
                "heldNames": held_names(self.held),
                "permission": self.modifier_permission,
            },
            "perKey": {
                "supported": self.per_key,
                "push": self.config["per_key"]["push_to_keyboard"],
                "highlights": self.config["per_key"]["enabled"],
                "reason": self.per_key_reason,
                "timeoutMs": (self.per_key_caps or {}).get("timeout_ms"),
            },
            "music": {
                "enabled": self.config["music"]["enabled"],
                "effect": self.config["music"]["effect"],
                "mode": "per-key" if self.per_key else "via",
                "error": self.music_error,
            },
            "profile": {
                "id": profile["id"] if profile else "",
                "name": profile["name"] if profile else "",
                "windowClass": self.window_class,
                "windowTitle": self.window_title,
                "submap": self.submap,
            },
            "homeAssistant": {
                "enabled": section["enabled"],
                "url": section["url"],
                "entities": section["entities"],
                "tokenEnv": section["token_env"],
                "tokenFile": section["token_file"],
                "configured": token_set,
                "syncBrightness": section["sync_brightness"],
                "onlyWhenOn": section["only_when_on"],
                "lastError": self.ha_error,
                "lastPushed": self.ha_pushed,
            },
            "hardware": self.hardware,
            "conflicts": self.conflicts,
            "backup": self.keymap_backup,
            "verification": verification_notes(self.per_key),
            "deviceIdentity": self.device_identity,
        }
        if include_keymap and self.keymap:
            body["keymap"] = {
                "known": True,
                "layers": self.keymap["layers"],
                "keys": self.keymap["keys"],
                "codes": catalog(),
            }
        else:
            body["keymap"] = {"known": bool(self.keymap), "layers": self.keymap["layers"] if self.keymap else LAYER_COUNT}
        return body


def _scale(color, scale):
    from air96_protocol import hex_to_rgb
    red, green, blue = hex_to_rgb(color)
    return tuple(max(0, min(255, round(channel * scale))) for channel in (red, green, blue))


def checkout_revision(root):
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or b"").decode("utf-8", "replace").strip()


def running_worker_processes():
    root = Path("/proc")
    found = []
    if not root.is_dir():
        return found
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        text = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if "air96_worker.py" not in text:
            continue
        found.append({"pid": int(entry.name), "cmdline": text})
    return found


def read_worker_heartbeat(state_dir, now=None):
    path = Path(state_dir) / "worker.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    moment = time.time() if now is None else now
    updated = float(data.get("updated") or 0)
    data["fresh"] = moment - updated < 3
    return data


def describe_runtime(backend, heartbeat=None, processes=None):
    """Plain reasons for a dark keyboard. Status prints these as well as JSON."""
    if heartbeat is None:
        heartbeat = read_worker_heartbeat(backend.state_dir)
    if processes is None:
        processes = running_worker_processes()
    here = Path(__file__).resolve().parent
    our_revision = checkout_revision(here)
    lines = []
    script = ""
    fresh = bool(heartbeat and heartbeat.get("fresh"))
    matches = False
    if fresh:
        script = str(heartbeat.get("script") or "")
        try:
            matches = bool(script) and Path(script).resolve().parent == here
        except OSError:
            matches = False
        revision = str(heartbeat.get("revision") or "")
        if matches and our_revision and revision and revision != our_revision:
            matches = False
            lines.append(
                f"The bar worker is revision {revision} and this checkout is {our_revision}. "
                "Run ./install.sh so the worker restarts on this code."
            )
        elif matches:
            lines.append(f"The bar worker is this checkout{f' ({revision})' if revision else ''}.")
        else:
            lines.append(
                f"The bar worker is {script or 'another copy'}, not this checkout. "
                "git pull here does not update it. ./install.sh points the plugin at this checkout and restarts the worker."
            )
    elif processes:
        lines.append(
            "An air96_worker.py process is running but it is not the current plugin. "
            f"Command: {processes[0]['cmdline']}. ./install.sh replaces a copied plugin and restarts the worker."
        )
    else:
        lines.append(
            "No bar worker is running. Super highlights and music are sent by that process. "
            "`music on` only saves the setting. ./install.sh links the plugin; then enable it and restart the shell if the bar is not up."
        )

    push = bool(backend.config["per_key"]["push_to_keyboard"])
    music_on = bool(backend.config["music"]["enabled"])
    if not push:
        lines.append(
            "Per-key push is off in the saved config. The first plugin wrote that default, and turning the "
            "default on later does not change the file. Nothing is sent for Super highlights. "
            "Run: python3 air96_cli.py push on"
        )
    elif backend.per_key is False:
        lines.append("This keyboard did not accept per-key colors, so individual keys are not painted.")
    elif music_on:
        lines.append(
            "Music mode is on, so the visualizer owns the keys and Super highlights are not drawn. "
            "Run: python3 air96_cli.py music off"
        )
    elif not fresh:
        lines.append("Push is on in this config, but no current worker is sending frames to the keyboard.")
    else:
        lines.append(
            "Super highlights use the modifier mask the keyboard reports. The optional evdev udev rule is not required."
        )

    if getattr(backend, "mods_from_keyboard", None) is True:
        from air96_binds import held_names
        names = "+".join(held_names(backend.held)) or "none"
        lines.append(f"The keyboard reports modifiers: {names}.")
    elif backend.per_key and getattr(backend, "mods_from_keyboard", None) is False:
        lines.append(
            "The keyboard did not answer the modifier report (0xA9). Super+Shift cannot change the highlights "
            "until this keymap is running. The evdev rule is only a fallback."
        )

    if music_on and fresh:
        recorder = " ".join(heartbeat.get("recorder") or [])
        if heartbeat.get("musicError"):
            lines.append(f"Music: {heartbeat.get('musicError')}")
        elif heartbeat.get("stalled"):
            lines.append("Music is on, but the recorder has stopped sending samples. The lights keep the last frame unless they are faded.")
        else:
            rms = heartbeat.get("rms")
            detail = f" rms={rms:.3f}" if isinstance(rms, (int, float)) else ""
            lines.append(f"Music is playing through the worker.{detail} Source: {recorder or 'not started'}.")
    elif music_on:
        lines.append("Music is saved as on. Only the bar worker opens the speaker monitor. `music on` does not play it.")

    theme = backend.theme_color()
    stored = backend.config["lighting"]["hex"]
    if backend.config["lighting"]["follow_theme"] and theme and theme.lower() != stored.lower():
        lines.append(
            f"Theme follow is on, so the keyboard color is the theme {theme}. "
            f"lighting.hex {stored} is only the stored color and is not what follow writes."
        )

    runtime = {
        "workerMatches": matches,
        "workerFresh": fresh,
        "workerScript": script,
        "revision": our_revision,
        "push": push,
        "music": music_on,
    }
    return {"lines": lines, "runtime": runtime}
