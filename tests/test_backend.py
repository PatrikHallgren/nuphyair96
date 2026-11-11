import json
import math
import unittest
from unittest.mock import patch

from support import BackendCase
from air96_audio import analyze
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
        self.assertEqual(self.backend.snapshot()["perKey"]["timeoutMs"], 2000)
        self.backend.clear_per_key()
        self.assertEqual(self.backend.frame_kind, "")

    def test_stock_music_pulse_is_not_saved(self):
        self.connect(per_key=False)
        samples = [0.6 * math.sin(2 * math.pi * 80 * i / 16000) for i in range(512)]
        saved = self.keyboard.saved
        self.backend.push_music(analyze(samples))
        self.assertEqual(self.keyboard.saved, saved)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertGreater(self.keyboard.brightness, 8)
        self.assertIn("not saved", self.backend.message)

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
