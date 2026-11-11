import json
import unittest

import support  # noqa: F401
from air96_ha import (
    HomeAssistantError,
    resolve_token,
    send,
    service_request,
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
        payload = turn_on_payload(["light.desk", "light.room"], "#7aa2f7", 180)
        self.assertEqual(payload["entity_id"], ["light.desk", "light.room"])
        self.assertEqual(payload["rgb_color"], [0x7a, 0xa2, 0xf7])
        self.assertEqual(payload["brightness"], 180)
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


if __name__ == "__main__":
    unittest.main()
