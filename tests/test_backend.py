import json
import unittest

from support import BackendCase
from air96_backend import validate_config
from air96_worker import execute


class BackendTests(BackendCase):
    def test_theme_follow_sends_solid_color_and_saves(self):
        (self.theme / "keyboard.rgb").write_text("ff00ff\n")
        self.connect()
        self.backend.apply_lighting({
            "follow_theme": True,
            "solid_when_following": True,
            "effect": 12,
            "brightness": 200,
            "speed": 10,
        }, force=True)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertEqual(self.keyboard.brightness, 200)
        self.assertEqual(self.keyboard.saved, 1)
        self.assertGreater(self.keyboard.sat, 200)
        self.backend.apply_lighting(force=False)
        self.assertEqual(self.keyboard.saved, 1)
        self.backend.sync(force=True)
        self.assertEqual(self.keyboard.saved, 2)

    def test_follow_off_does_not_touch_the_keyboard_on_sync(self):
        self.connect()
        self.backend.sync()
        self.assertEqual(self.keyboard.saved, 0)
        self.assertIn("off", self.backend.message)

    def test_snapshot_hides_the_token(self):
        self.backend.update_settings({"home_assistant": {
            "enabled": False,
            "url": "http://ha.local:8123",
            "entities": ["light.desk"],
            "token": "super-secret-token",
        }})
        dumped = json.dumps(self.backend.snapshot())
        self.assertNotIn("super-secret-token", dumped)
        self.assertTrue(self.backend.snapshot()["homeAssistant"]["configured"])
        self.assertEqual(oct((self.backend.config_path.stat().st_mode) & 0o777), "0o600")

    def test_stock_probe_reports_per_key_unavailable(self):
        self.connect(per_key=False)
        self.assertIs(self.backend.per_key, False)
        self.assertIn("Stock VIA", self.backend.per_key_reason)
        with self.assertRaises(Exception):
            self.backend.push_per_key()

    def test_custom_firmware_accepts_a_frame(self):
        (self.theme / "colors.toml").write_text('accent = "#7aa2f7"\n')
        self.connect(per_key=True)
        self.assertIs(self.backend.per_key, True)
        self.backend.binds = [{
            "key": "q", "modmask": 64, "submap": "", "label": "Close", "dispatcher": "killactive", "arg": "",
        }]
        self.backend.update_settings({"per_key": {"push_to_keyboard": True}})
        self.backend.push_per_key()
        self.assertGreaterEqual(len(self.keyboard.frames), 12)
        self.assertTrue(all(frame[0] == 0xA7 for frame in self.keyboard.frames))

    def test_keymap_roundtrip_and_conflict(self):
        self.connect()
        self.backend.load_keymap()
        esc = self.backend.keymap["keys"]["0:0:0"]
        self.assertEqual(esc["value"], 0x04)
        self.backend.apply_keymap([{"layer": 0, "row": 0, "col": 0, "original": 0x04, "value": 0x29}])
        self.assertEqual(self.keyboard.keycode(0, 0, 0), 0x29)
        self.assertTrue(self.backend.keymap_backup.endswith(".json"))
        self.keyboard.blob[1] = 0x05  # external change
        self.backend.apply_keymap([{"layer": 0, "row": 0, "col": 0, "original": 0x29, "value": 0x1E}])
        self.assertEqual(self.keyboard.keycode(0, 0, 0), 0x05)
        self.assertEqual(self.backend.conflicts[0]["current"], 0x05)
        self.assertIn("nothing was written", self.backend.error)

    def test_execute_reports_a_missing_keyboard(self):
        result = execute(self.backend, {"action": "apply", "config": {"hex": "#112233"}})
        self.assertIn("not connected", result["error"].lower())
        self.assertNotIn("super-secret-token", json.dumps(result))

    def test_rejects_unknown_config(self):
        with self.assertRaises(ValueError):
            validate_config({"lighting": {"direction": "left"}})


if __name__ == "__main__":
    unittest.main()
