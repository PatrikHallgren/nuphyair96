import json
import os
import unittest

import support  # noqa: F401
from air96_binds import compose_highlights, key_to_id, parse_bind_lines, parse_hyprctl_binds
from air96_hid import EvdevModifiers

HYPR = [
    {"modmask": 64, "submap": "", "key": "Q", "description": "Close window", "dispatcher": "killactive", "arg": ""},
    {"modmask": 65, "submap": "", "key": "Return", "description": "Terminal", "dispatcher": "exec", "arg": "alacritty"},
    {"modmask": 64, "submap": "resize", "key": "H", "description": "Resize left", "dispatcher": "resizeactive", "arg": "-20 0"},
    {"modmask": 0, "submap": "", "key": "F1", "description": "Help", "dispatcher": "exec", "arg": "help"},
    {"mouse": True, "modmask": 64, "submap": "", "key": "mouse:272", "description": "Drag", "dispatcher": "movewindow", "arg": ""},
]


class BindTests(unittest.TestCase):
    def test_hyprctl_json_and_idle_super_keys(self):
        binds = parse_hyprctl_binds(json.dumps(HYPR))
        self.assertEqual({item["key"] for item in binds}, {"q", "enter", "h", "f1"})
        idle = compose_highlights(binds, held=0, color="#7aa2f7")
        self.assertEqual(idle["q"]["level"], "idle")
        self.assertNotIn("enter", idle)
        self.assertNotIn("h", idle)
        self.assertNotIn("f1", idle)

    def test_held_super_lights_only_exact_binds(self):
        binds = parse_hyprctl_binds(HYPR)
        active = compose_highlights(binds, held=64)
        self.assertEqual(set(active), {"q"})
        self.assertEqual(active["q"]["level"], "active")
        both = compose_highlights(binds, held=65)
        self.assertEqual(set(both), {"enter"})
        self.assertIn("Terminal", both["enter"]["label"])

    def test_submap(self):
        binds = parse_hyprctl_binds(HYPR)
        resize = compose_highlights(binds, held=64, submap="resize")
        self.assertEqual(set(resize), {"h"})

    def test_bind_lines_and_code_keys(self):
        text = """
        bind = SUPER, Q, killactive
        bindd = SUPER SHIFT, Return, Open a terminal, exec, alacritty
        bind = SUPER, mouse:272, movewindow
        bind = SUPER, code:24, exec, q-by-code
        # bind = SUPER, F, ignored
        """
        binds = parse_bind_lines(text)
        self.assertEqual(binds[0]["key"], "q")
        self.assertEqual(binds[0]["modmask"], 64)
        self.assertEqual(binds[0]["label"], "killactive")
        self.assertEqual(binds[1]["label"], "Open a terminal")
        coded = [item for item in binds if "q-by-code" in item["arg"]]
        self.assertEqual(coded[0]["key"], "q")

    def test_key_names(self):
        self.assertEqual(key_to_id("Escape"), "esc")
        self.assertEqual(key_to_id("KP_7"), "kp7")
        self.assertEqual(key_to_id("code:36"), "enter")
        self.assertEqual(key_to_id("code:65"), "space")
        self.assertIsNone(key_to_id("Super_L"))
        self.assertIsNone(key_to_id("mouse_down"))

    def test_profile_keys_yield_to_an_active_bind(self):
        binds = parse_hyprctl_binds(HYPR)
        profile = {"name": "Firefox", "keys": [
            {"key": "q", "mods": ["ctrl"], "label": "Quit", "color": "#f7768e"},
            {"key": "t", "mods": ["ctrl"], "label": "New tab", "color": "#89b4fa"},
        ]}
        shown = compose_highlights(binds, held=0, profile=profile, color="#ffffff")
        self.assertEqual(shown["q"]["source"], "bind")
        self.assertEqual(shown["t"]["source"], "profile")
        self.assertIn("ctrl", shown["t"]["label"])
        held = compose_highlights(binds, held=64, profile=profile, color="#ffffff")
        self.assertNotIn("t", held)
        self.assertEqual(held["q"]["source"], "bind")

    def test_omarchy_combos_follow_the_full_mask(self):
        # Same shape as Omarchy's tiling binds: Super for an action, Super+Shift
        # for the paired action, Super+Alt for another, and a mouse bind ignored.
        text = """
        bind = SUPER, W, killactive
        bind = SUPER, J, togglesplit
        bind = SUPER, left, movefocus, l
        bind = SUPER SHIFT, left, swapwindow, l
        bind = SUPER, code:10, workspace, 1
        bind = SUPER SHIFT, code:10, movetoworkspace, 1
        bind = SUPER ALT, code:19, workspace, 10
        bind = SUPER SHIFT ALT, Return, exec, omarchy-menu
        bind = SUPER, mouse:272, movewindow
        """
        binds = parse_bind_lines(text)
        self.assertEqual(key_to_id("code:10"), "1")
        self.assertEqual(key_to_id("code:19"), "0")
        self.assertEqual(key_to_id("code:20"), "minus")
        idle = compose_highlights(binds, held=0)
        self.assertEqual(set(idle), {"w", "j", "left", "1"})
        super_only = compose_highlights(binds, held=64)
        self.assertEqual(set(super_only), {"w", "j", "left", "1"})
        self.assertTrue(all(item["level"] == "active" for item in super_only.values()))
        shifted = compose_highlights(binds, held=64 | 1)
        self.assertEqual(set(shifted), {"left", "1"})
        alt = compose_highlights(binds, held=64 | 8)
        self.assertEqual(set(alt), {"0"})
        both = compose_highlights(binds, held=64 | 1 | 8)
        self.assertEqual(set(both), {"enter"})
        self.assertEqual(compose_highlights(binds, held=64 | 4), {})

    def test_evdev_tracks_modifiers_and_discards_other_keys(self):
        def event(code, value):
            data = bytearray(24)
            data[16:18] = (1).to_bytes(2, "little")
            data[18:20] = code.to_bytes(2, "little")
            data[20:24] = value.to_bytes(4, "little", signed=True)
            return bytes(data)

        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        modifiers = EvdevModifiers()
        modifiers.fds = [read_fd]
        try:
            os.write(write_fd, event(16, 1))  # KEY_Q, must not affect the mask
            modifiers.drain()
            self.assertEqual(modifiers.mask, 0)
            os.write(write_fd, event(125, 1) + event(42, 1))
            modifiers.drain()
            self.assertEqual(modifiers.mask, 64 | 1)
            os.write(write_fd, event(125, 0))
            modifiers.drain()
            self.assertEqual(modifiers.mask, 1)
        finally:
            os.close(read_fd)
            os.close(write_fd)


if __name__ == "__main__":
    unittest.main()
