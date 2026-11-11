import unittest

import support  # noqa: F401
from air96_keycodes import keycode_name, keycode_short, keycode_value
from air96_layout import (
    KEY_LED_COUNT,
    KEYS,
    LED_COUNT,
    MATRIX_COLS,
    MATRIX_ROWS,
    PRODUCT_IDS,
    SIDE_LED_START,
    VENDOR_ID,
    key_by_id,
    led_for_matrix,
)
from air96_protocol import (
    EFFECTS,
    PACKET_SIZE,
    buffer_request,
    hex_to_qmk_hs,
    keymap_offset,
    lighting_get,
    lighting_save,
    lighting_set,
    normalize_hex,
    parse_buffer,
    parse_keycode,
    parse_protocol_version,
    per_key_probe_request,
    per_key_set_packets,
    per_key_supported,
    protocol_version_request,
    set_keycode_request,
)


class ProtocolTests(unittest.TestCase):
    def test_layout_matches_the_qmk_matrix(self):
        self.assertEqual(len(KEYS), 100)
        self.assertEqual(len({key["id"] for key in KEYS}), 100)
        self.assertEqual(LED_COUNT, 110)
        self.assertEqual(KEY_LED_COUNT, 100)
        self.assertEqual(SIDE_LED_START, 100)
        self.assertEqual((MATRIX_ROWS, MATRIX_COLS), (6, 21))
        self.assertEqual(VENDOR_ID, 0x19F5)
        self.assertEqual(PRODUCT_IDS, (0x3265, 0x3266))
        esc = key_by_id("esc")
        self.assertEqual((esc["row"], esc["col"], esc["led"]), (0, 0, 0))
        q = key_by_id("q")
        self.assertEqual((q["row"], q["col"]), (2, 1))
        self.assertEqual(led_for_matrix(2, 1), q["led"])
        self.assertEqual([key["led"] for key in KEYS], list(range(100)))
        self.assertGreater(key_by_id("space")["w"], 6)
        self.assertEqual(key_by_id("kp_enter")["h"], 2)

    def test_via_lighting_packets(self):
        self.assertEqual(len(EFFECTS), 41)
        self.assertEqual(EFFECTS[0], "All Off")
        self.assertEqual(EFFECTS[1], "Solid Color")
        self.assertEqual(EFFECTS[-1], "Solid MultiSplash")
        color = lighting_set(4, 212, 255)
        self.assertEqual(color[:5], bytes((0x07, 0x03, 0x04, 212, 255)))
        self.assertEqual(len(color), PACKET_SIZE)
        self.assertEqual(lighting_get(1)[:3], bytes((0x08, 0x03, 0x01)))
        self.assertEqual(lighting_save()[0], 0x09)
        self.assertEqual(hex_to_qmk_hs("#ff0000"), (0, 255))
        hue, sat = hex_to_qmk_hs("#0000ff")
        self.assertGreater(hue, 150)
        self.assertEqual(sat, 255)
        self.assertEqual(hex_to_qmk_hs("#ffffff")[1], 0)
        self.assertEqual(normalize_hex("FF00FF"), "#ff00ff")

    def test_keymap_addressing_is_big_endian(self):
        # layer 1, row 2, col 3 in a 6x21 matrix
        offset = keymap_offset(1, 2, 3, 6, 21)
        self.assertEqual(offset, (1 * 6 * 21 + 2 * 21 + 3) * 2)
        request = set_keycode_request(1, 2, 3, 0x5221)
        self.assertEqual(request[:6], bytes((0x05, 1, 2, 3, 0x52, 0x21)))
        response = bytearray(32)
        response[:6] = bytes((0x04, 1, 2, 3, 0x00, 0x04))
        self.assertEqual(parse_keycode(response, 1, 2, 3), 0x04)
        chunk = buffer_request(offset, 2)
        echo = bytearray(chunk)
        echo[4:6] = bytes((0x00, 0x1E))
        self.assertEqual(parse_buffer(echo, offset, 2), bytes((0x00, 0x1E)))

    def test_protocol_version_and_per_key_probe(self):
        version = bytearray(protocol_version_request())
        version[1] = 0x00
        version[2] = 0x0C
        self.assertEqual(parse_protocol_version(version), 0x000C)
        probe = per_key_probe_request()
        self.assertEqual(probe[:6], bytes((0xA6, ord("A"), ord("9"), ord("6"), ord("K"), 1)))
        stock = bytearray(probe)
        stock[0] = 0xFF
        self.assertFalse(per_key_supported(stock))
        ack = bytearray(32)
        ack[0] = 0xA6
        ack[1:5] = b"A96K"
        ack[5] = 1
        self.assertTrue(per_key_supported(ack))
        packets = per_key_set_packets([(1, 2, 3)] * 10)
        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0][0], 0xA7)
        self.assertEqual(packets[0][1], 0)
        self.assertEqual(packets[0][2], 9)
        self.assertEqual(packets[1][2], 1)

    def test_keycode_names(self):
        self.assertEqual(keycode_value("KC_A"), 0x04)
        self.assertEqual(keycode_value("KC_ESC"), 0x29)
        self.assertEqual(keycode_name(0x29), "KC_ESC")
        self.assertEqual(keycode_short(0x29), "Esc")
        self.assertEqual(keycode_value("MO(1)"), 0x5221)
        self.assertEqual(keycode_short(0x5221), "Fn1")
        self.assertEqual(keycode_value("RF_DFU"), 0x7E00)
        self.assertEqual(keycode_name(0x7E0F), "SIDE_MOD")
        self.assertEqual(keycode_value("KC_TRANSPARENT"), 1)


if __name__ == "__main__":
    unittest.main()
