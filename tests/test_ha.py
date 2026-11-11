import json
import unittest

import support  # noqa: F401
from air96_ha import (
    HomeAssistantError,
    light_is_on,
    prepare_token,
    resolve_token,
    sanitize_token,
    send,
    service_request,
    state_request,
    turn_on_payload,
)


class FakeResponse:
    status = 200

    def __init__(self):
        self._read = False

    def read(self, _limit):
        return b"[]"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class HaTests(unittest.TestCase):
    def test_payload_uses_rgb_and_not_the_token(self):
        payload = turn_on_payload(["light.desk", "light.room"], "#7aa2f7")
        self.assertEqual(payload["entity_id"], ["light.desk", "light.room"])
        self.assertEqual(payload["rgb_color"], [0x7a, 0xa2, 0xf7])
        self.assertNotIn("brightness", payload)
        explicit = turn_on_payload(["light.desk"], "#7aa2f7", 180)
        self.assertEqual(explicit["brightness"], 180)
        prepared = service_request("http://homeassistant.local:8123/", "a-real-token-value", payload)
        self.assertEqual(prepared["url"], "http://homeassistant.local:8123/api/services/light/turn_on")
        self.assertTrue(prepared["headers"]["Authorization"].startswith("Bearer "))
        body = json.loads(prepared["body"])
        self.assertNotIn("token", json.dumps(body))
        self.assertNotIn("a-real-token-value", prepared["body"].decode())

    def test_rejects_non_lights_and_bad_urls(self):
        with self.assertRaises(HomeAssistantError):
            turn_on_payload(["switch.desk"], "#ffffff", 10)
        with self.assertRaises(HomeAssistantError):
            service_request("file:///tmp/ha", "a-real-token-value", turn_on_payload(["light.desk"], "#ffffff", 1))

    def test_token_resolution_order_and_send(self):
        self.assertEqual(resolve_token({"HA_TOKEN": "from-env-token"}, "HA_TOKEN", "", "inline-token-value"), "inline-token-value")
        self.assertEqual(resolve_token({"HA_TOKEN": "from-env-token"}, "HA_TOKEN", ""), "from-env-token")
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["auth"] = request.get_header("Authorization")
            return FakeResponse()

        payload = turn_on_payload("light.desk", "#ffffff", 10)
        prepared = service_request("https://ha.example", "from-env-token", payload)
        result = send(prepared, opener=opener, timeout=2)
        self.assertEqual(result["status"], 200)
        self.assertEqual(captured["url"], "https://ha.example/api/services/light/turn_on")
        self.assertEqual(captured["timeout"], 2)
        self.assertIn("from-env-token", captured["auth"])

    def test_paste_markers_are_removed_and_bad_tokens_stay_unprinted(self):
        secret = "a-real-token-value"
        wrapped = "\x1b[200~  " + secret + "  \x1b[201~\n"
        self.assertEqual(sanitize_token(wrapped), secret)
        self.assertEqual(prepare_token(wrapped), secret)
        path = self._token_file(wrapped)
        self.assertEqual(resolve_token({}, "HA_TOKEN", str(path)), secret)
        payload = turn_on_payload(["light.desk"], "#ffffff", 10)
        prepared = service_request("http://ha.example", wrapped, payload)
        self.assertEqual(prepared["headers"]["Authorization"], "Bearer " + secret)
        self.assertNotIn(secret, prepared["body"].decode())

        junk = "UNIQUESECRETVALUE\x01still-bad"
        with self.assertRaises(HomeAssistantError) as malformed:
            prepare_token("\x1b[200~" + junk + "\x1b[201~")
        self.assertIn("malformed", str(malformed.exception))
        self.assertIn("control", str(malformed.exception))
        self.assertNotIn("UNIQUESECRETVALUE", str(malformed.exception))

        with self.assertRaises(HomeAssistantError) as short:
            prepare_token("abc")
        self.assertIn("too short", str(short.exception))
        self.assertNotIn("abc", str(short.exception))

        with self.assertRaises(HomeAssistantError) as spaces:
            prepare_token("token value that is long enough")
        self.assertIn("whitespace", str(spaces.exception))
        self.assertNotIn("token value", str(spaces.exception))

        with self.assertRaises(HomeAssistantError) as missing:
            prepare_token("  \n")
        self.assertIn("missing", str(missing.exception))
        self.assertNotIn("malformed", str(missing.exception))

        with self.assertRaises(HomeAssistantError) as markers:
            prepare_token("\x1b[200~\x1b[201~\n")
        self.assertIn("malformed", str(markers.exception))

        with self.assertRaises(HomeAssistantError) as unreadable:
            resolve_token({}, "HA_TOKEN", str(path.parent / "missing-token"))
        self.assertIn("unreadable", str(unreadable.exception))
        self.assertNotIn(secret, str(unreadable.exception))

    def test_color_push_omits_brightness_and_an_off_light_is_not_on(self):
        self.assertFalse(light_is_on('{"state": "off", "attributes": {"brightness": 180}}'))
        self.assertTrue(light_is_on({"state": "on", "attributes": {"brightness": 40}}))
        self.assertFalse(light_is_on({"state": "unavailable"}))
        with self.assertRaises(HomeAssistantError):
            light_is_on("[]")
        captured = {}

        def opener(request, timeout):
            captured["method"] = request.get_method()
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            return FakeResponse()

        prepared = state_request("http://ha.example", "from-env-token", "light.floor_lamp_66fa")
        send(prepared, opener=opener, timeout=2)
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["url"], "http://ha.example/api/states/light.floor_lamp_66fa")
        self.assertNotIn("from-env-token", captured["url"])
        self.assertIn("from-env-token", captured["auth"])

        class LongState:
            status = 200

            def read(self, limit):
                self.limit = limit
                payload = json.dumps({
                    "state": "off",
                    "attributes": {"friendly_name": "floor lamp", "effect_list": ["x" * 800]},
                }).encode()
                return payload[:limit]

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        long_state = LongState()
        result = send(prepared, opener=lambda _request, timeout: long_state, timeout=2)
        self.assertGreater(long_state.limit, 1000)
        self.assertFalse(light_is_on(result["body"]))

    def _token_file(self, text):
        import tempfile
        from pathlib import Path
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "ha-token"
        path.write_text(text)
        return path


if __name__ == "__main__":
    unittest.main()
