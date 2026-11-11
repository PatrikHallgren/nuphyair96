import json
import unittest
from unittest.mock import patch

from support import BackendCase
from air96_backend import validate_config
from air96_screensaver import command_is_screensaver, screensaver_running
from air96_worker import drive_lights, execute


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
        self.backend.update_settings({"lighting": {"follow_theme": False}})
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
        self.assertFalse(self.backend.snapshot()["homeAssistant"]["syncBrightness"])
        self.assertTrue(self.backend.snapshot()["homeAssistant"]["onlyWhenOn"])
        self.assertEqual(oct((self.backend.config_path.stat().st_mode) & 0o777), "0o600")

    def test_color_push_keeps_lamp_brightness_and_skips_an_off_light(self):
        loaded = validate_config({"home_assistant": {
            "url": "http://ha.local:8123",
            "entities": ["light.floor_lamp_66fa"],
        }})
        self.assertFalse(loaded["home_assistant"]["sync_brightness"])
        self.assertTrue(loaded["home_assistant"]["only_when_on"])
        self.backend.update_settings({"home_assistant": {
            "enabled": True,
            "url": "http://ha.local:8123",
            "entities": ["light.floor_lamp_66fa", "light.desk"],
            "token": "super-secret-token",
        }, "lighting": {"brightness": 180, "hex": "#112233", "follow_theme": False}})
        calls = []

        def fake_send(prepared, opener=None, timeout=5):
            calls.append(prepared)
            entity = prepared["url"].rsplit("/", 1)[-1]
            state = "off" if entity == "light.floor_lamp_66fa" else "on"
            if prepared["method"] == "GET":
                return {"status": 200, "body": json.dumps({"state": state, "entity_id": entity})}
            return {"status": 200, "body": "[]"}

        self.connect()
        with patch("air96_backend.send_ha", fake_send):
            self.backend.apply_lighting(force=True)
        self.assertEqual(self.keyboard.brightness, 180)
        posted = [call for call in calls if call["method"] == "POST"]
        self.assertEqual(len(posted), 1)
        body = json.loads(posted[0]["body"])
        self.assertEqual(body["entity_id"], ["light.desk"])
        self.assertEqual(body["rgb_color"], [0x11, 0x22, 0x33])
        self.assertNotIn("brightness", body)
        self.assertNotIn("super-secret-token", posted[0]["body"].decode())
        self.assertIn("left off: light.floor_lamp_66fa", self.backend.message)

        calls.clear()
        self.backend.update_settings({"home_assistant": {"entities": ["light.floor_lamp_66fa"]}})
        with patch("air96_backend.send_ha", fake_send):
            self.backend.push_home_assistant()
        self.assertEqual([call["method"] for call in calls], ["GET"])
        self.assertIn("color not pushed", self.backend.message)
        self.assertNotIn("super-secret-token", self.backend.message)

        calls.clear()
        self.backend.update_settings({
            "home_assistant": {"sync_brightness": True, "only_when_on": False, "entities": ["light.floor_lamp_66fa"]},
            "lighting": {"hex": "#778899", "brightness": 180},
        })

        def post_only(prepared, opener=None, timeout=5):
            calls.append(prepared)
            return {"status": 200, "body": "[]"}

        with patch("air96_backend.send_ha", post_only):
            self.backend.push_home_assistant()
        self.assertEqual([call["method"] for call in calls], ["POST"])
        body = json.loads(calls[0]["body"])
        self.assertEqual(body["brightness"], 180)
        self.assertEqual(body["entity_id"], ["light.floor_lamp_66fa"])
        self.assertNotIn("super-secret-token", calls[0]["body"].decode())

    def test_stock_probe_reports_per_key_unavailable(self):
        self.connect(per_key=False)
        self.assertIs(self.backend.per_key, False)
        self.assertIn("Stock VIA", self.backend.per_key_reason)
        self.assertNotIn(0xA8, self.keyboard.commands)

    def test_custom_firmware_is_cleared_then_painted_solid(self):
        (self.theme / "keyboard.rgb").write_text("00ff00\n")
        self.connect(per_key=True)
        self.assertIs(self.backend.per_key, True)
        self.assertIn(0xA8, self.keyboard.commands)
        self.assertNotIn(0xA7, self.keyboard.commands)
        self.keyboard.commands.clear()
        self.backend.apply_lighting({"follow_theme": True, "brightness": 90}, force=True)
        self.assertEqual(self.keyboard.commands[0], 0xA8)
        self.assertNotIn(0xA7, self.keyboard.commands)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertEqual(self.keyboard.brightness, 90)
        self.assertEqual(self.keyboard.saved, 1)

    def test_screensaver_breathing_is_not_saved_and_solid_returns(self):
        (self.theme / "keyboard.rgb").write_text("ff00ff\n")
        self.connect()
        self.backend.update_settings({"screensaver": {"enabled": True}})
        self.backend.apply_lighting(force=True)
        saved = self.keyboard.saved
        self.assertEqual(self.keyboard.effect, 1)
        self.backend.note_screensaver(True)
        self.assertEqual(self.keyboard.effect, 4)
        self.assertEqual(self.keyboard.saved, saved)
        self.assertFalse(self.backend.note_screensaver(True))
        self.backend.note_screensaver(False)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertEqual(self.keyboard.saved, saved)

    def test_drive_lights_waits_a_second_between_screensaver_checks(self):
        (self.theme / "keyboard.rgb").write_text("ff00ff\n")
        self.connect()
        self.backend.update_settings({"screensaver": {"enabled": True}})
        self.backend.apply_lighting(force=True)
        saved = self.keyboard.saved
        state = {"screen": 0.0}
        with patch("air96_worker.screensaver_running", return_value=True):
            drive_lights(self.backend, state, 10)
        self.assertEqual(self.keyboard.effect, 4)
        self.assertEqual(self.keyboard.saved, saved)
        with patch("air96_worker.screensaver_running", return_value=False):
            drive_lights(self.backend, state, 10.2)
            self.assertEqual(self.keyboard.effect, 4)
            drive_lights(self.backend, state, 12)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertEqual(self.keyboard.saved, saved)

    def test_screensaver_process_scan_ignores_the_worker(self):
        self.assertTrue(command_is_screensaver("kitty --class org.omarchy.screensaver omarchy-screensaver"))
        self.assertTrue(command_is_screensaver("omarchy-launch-screensaver"))
        self.assertFalse(command_is_screensaver("python3 /home/me/.config/omarchy/plugins/local.nuphy-air96/air96_worker.py"))
        root = self.backend.state_dir / "proc"
        (root / "42").mkdir(parents=True)
        (root / "42" / "cmdline").write_bytes(b"omarchy-launch-screensaver\x00")
        (root / "7").mkdir()
        (root / "7" / "cmdline").write_bytes(b"python3\x00air96_worker.py\x00")
        self.assertTrue(screensaver_running(root))

    def test_legacy_sections_are_ignored(self):
        loaded = validate_config({
            "music": {"enabled": True},
            "per_key": {"push_to_keyboard": True},
            "modifiers": {"enabled": True},
            "profiles": {"enabled": True},
            "lighting": {"follow_theme": False, "hex": "#010203"},
        })
        self.assertNotIn("music", loaded)
        self.assertNotIn("per_key", loaded)
        self.assertFalse(loaded["lighting"]["follow_theme"])
        self.assertEqual(loaded["lighting"]["hex"], "#010203")
        self.assertEqual(loaded["home_assistant"]["entities"], ["light.floor_lamp_66fa"])

    def test_manual_lamp_color_sends_its_own_brightness(self):
        self.backend.update_settings({"home_assistant": {
            "enabled": True,
            "url": "http://ha.local:8123",
            "entities": ["light.floor_lamp_66fa"],
            "token": "super-secret-token",
            "follow_theme": False,
            "hex": "#abcdef",
            "brightness": 40,
            "only_when_on": False,
        }})
        calls = []

        def post_only(prepared, opener=None, timeout=5):
            calls.append(prepared)
            return {"status": 200, "body": "[]"}

        with patch("air96_backend.send_ha", post_only):
            self.backend.push_home_assistant()
        body = json.loads(calls[0]["body"])
        self.assertEqual(body["rgb_color"], [0xAB, 0xCD, 0xEF])
        self.assertEqual(body["brightness"], 40)
        self.assertNotIn("super-secret-token", calls[0]["body"].decode())

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
        result = execute(self.backend, {"action": "apply", "config": {"hex": "#112233", "follow_theme": False}})
        self.assertIn("not connected", result["error"].lower())
        self.assertNotIn("super-secret-token", json.dumps(result))

    def test_rejects_unknown_config(self):
        with self.assertRaises(ValueError):
            validate_config({"lighting": {"direction": "left"}})


if __name__ == "__main__":
    unittest.main()
