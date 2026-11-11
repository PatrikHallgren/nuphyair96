import json
import math
import unittest
from unittest.mock import patch

from support import BackendCase
from air96_audio import analyze
from air96_backend import validate_config
from air96_layout import KEYS
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

    def test_super_shift_lights_a_different_key_and_stays_brighter(self):
        self.connect(per_key=True)
        self.backend.binds = [
            {"key": "q", "modmask": 64, "submap": "", "label": "Close", "dispatcher": "killactive", "arg": ""},
            {"key": "enter", "modmask": 65, "submap": "", "label": "Terminal", "dispatcher": "exec", "arg": ""},
            {"key": "a", "modmask": 64 | 1 | 8, "submap": "", "label": "Menu", "dispatcher": "exec", "arg": ""},
        ]
        self.keyboard.hypr_mods = 64
        self.backend.push_per_key()
        self.assertEqual(self.backend.held, 64)
        q = next(key for key in KEYS if key["id"] == "q")
        enter = next(key for key in KEYS if key["id"] == "enter")
        other = next(key for key in KEYS if key["id"] == "z")
        self.assertGreater(self.keyboard.colors[q["led"]][2], self.keyboard.colors[other["led"]][2] + 80)
        self.assertLess(self.keyboard.colors[enter["led"]][2], self.keyboard.colors[other["led"]][2] + 20)

        self.keyboard.hypr_mods = 64 | 1
        self.backend.push_per_key()
        self.assertEqual(self.backend.held, 65)
        self.assertGreater(self.keyboard.colors[enter["led"]][2], self.keyboard.colors[q["led"]][2] + 80)

        self.keyboard.hypr_mods = 64 | 1 | 8
        self.backend.push_per_key()
        a = next(key for key in KEYS if key["id"] == "a")
        self.assertEqual(self.backend.held, 64 | 1 | 8)
        self.assertGreater(self.keyboard.colors[a["led"]][2], self.keyboard.colors[q["led"]][2] + 80)
        self.assertGreater(self.keyboard.colors[a["led"]][2], self.keyboard.colors[enter["led"]][2] + 80)

    def test_music_deltas_do_not_clear_the_overlay(self):
        self.connect(per_key=True)
        loud = {"rms": 0.8, "bands": [1.0] + [0.0] * 15, "bass": 1.0, "highs": 0.0}
        self.backend.push_music(loud)
        first = len(self.keyboard.frames)
        self.assertGreaterEqual(first, 2)
        self.assertNotIn(0xA8, self.keyboard.commands)
        self.keyboard.frames.clear()
        self.backend.push_music(loud)
        self.assertEqual(self.keyboard.frames, [])
        self.assertEqual(self.keyboard.commands[-1], 0xA6)
        self.backend.push_music({"rms": 0.0, "bands": [0.0] * 16, "bass": 0.0, "highs": 0.0})
        self.assertNotIn(0xA8, self.keyboard.commands)
        self.assertGreater(len(self.keyboard.frames), 0)

    def test_music_frame_covers_every_key_not_only_the_left_third(self):
        self.connect(per_key=True)
        dark = {"rms": 0.0, "bands": [0.0] * 16, "bass": 0.0, "highs": 0.0, "loudness": 0.0}
        self.backend.push_music(dark)
        self.assertEqual(self.backend.last_led_count, 100)
        self.assertEqual(self.backend.last_led_index, 99)
        self.keyboard.frames.clear()
        hot = [0.0] * 16
        hot[-1] = 1.0
        self.backend.push_music({"rms": 1.0, "bands": hot, "bass": 1.0, "highs": 1.0, "loudness": 1.0})
        right = next(key for key in KEYS if key["id"] == "kp_enter")
        left = min(KEYS, key=lambda key: key["x"])
        self.assertGreater(self.keyboard.colors[right["led"]][0], 200)
        self.assertLess(self.keyboard.colors[left["led"]][0], 30)
        self.assertGreaterEqual(self.backend.last_led_index, right["led"])
        self.assertGreater(self.backend.last_led_count, 0)
        self.assertLess(self.backend.last_led_count, 100)
        self.assertTrue(any(
            frame[1] <= right["led"] < frame[1] + frame[2] for frame in self.keyboard.frames
        ))

    def test_music_off_restores_highlights_without_clearing_or_saving(self):
        from air96_audio import MusicSession
        from air96_worker import drive_lights

        self.connect(per_key=True)
        self.backend.binds = [{
            "key": "q", "modmask": 64, "submap": "", "label": "Close", "dispatcher": "killactive", "arg": "",
        }]
        self.backend.update_settings({
            "music": {"enabled": True},
            "per_key": {"push_to_keyboard": True},
        })
        self.backend.push_music({"rms": 0.8, "bands": [1.0] + [0.0] * 15, "bass": 1.0, "highs": 0.0})
        self.assertEqual(self.backend.frame_kind, "music")
        saved = self.keyboard.saved
        self.keyboard.commands.clear()
        self.keyboard.frames.clear()
        self.backend.update_settings({"music": {"enabled": False}})
        state = {"music": True, "push": True, "last_music": 0.0, "retry": 0.0}
        drive_lights(self.backend, MusicSession(), state, 10.0)
        self.assertFalse(state["music"])
        self.assertTrue(self.backend.config["per_key"]["push_to_keyboard"])
        self.assertNotIn(0xA8, self.keyboard.commands)
        self.assertEqual(self.keyboard.saved, saved)
        self.assertEqual(self.backend.frame_kind, "highlight")
        q = next(key for key in KEYS if key["id"] == "q")
        other = next(key for key in KEYS if key["id"] == "z")
        self.assertGreater(self.keyboard.colors[q["led"]][0], self.keyboard.colors[other["led"]][0] + 80)

        self.keyboard.hypr_mods = 64
        drive_lights(self.backend, MusicSession(), state, 11.0)
        self.assertEqual(self.backend.held, 64)
        self.assertEqual(self.backend.frame_kind, "highlight")
        self.assertGreater(self.keyboard.colors[q["led"]][0], 200)
        self.assertNotIn(0xA8, self.keyboard.commands)

    def test_music_off_retries_when_the_highlight_push_fails(self):
        from air96_audio import MusicSession
        from air96_worker import drive_lights

        self.connect(per_key=True)
        self.backend.binds = [{
            "key": "q", "modmask": 64, "submap": "", "label": "Close", "dispatcher": "killactive", "arg": "",
        }]
        self.backend.update_settings({"music": {"enabled": False}, "per_key": {"push_to_keyboard": True}})
        self.backend.frame_kind = "music"
        state = {"music": True, "push": True, "last_music": 0.0, "retry": 0.0}
        original = self.keyboard.transact
        failed = {"count": 0}

        def flaky(payload):
            if payload and payload[0] == 0xA7 and failed["count"] < 1:
                failed["count"] += 1
                raise TimeoutError("keyboard busy")
            return original(payload)

        self.keyboard.transact = flaky
        drive_lights(self.backend, MusicSession(), state, 20.0)
        self.assertTrue(state["music"])
        self.assertNotEqual(self.backend.frame_kind, "highlight")
        drive_lights(self.backend, MusicSession(), state, 21.0)
        self.assertFalse(state["music"])
        self.assertEqual(self.backend.frame_kind, "highlight")
        self.assertNotIn(0xA8, self.keyboard.commands)
        self.assertTrue(self.backend.config["per_key"]["push_to_keyboard"])

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
