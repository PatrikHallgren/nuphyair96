import unittest

from air96_per_key import PerKeyController
from air96_protocol import (
    lighting_get,
    protocol_version_request,
    VAL_EFFECT,
    per_key_capabilities,
    per_key_clear_request,
    per_key_delta_packets,
    per_key_mods_request,
    per_key_probe_request,
    per_key_set_packets,
    per_key_supported,
    parse_per_key_mods,
)
from support import ROOT


class PerKeyTests(unittest.TestCase):
    def test_firmware_header_matches_the_host_constants(self):
        header = (ROOT / "firmware/keymaps/omarchy/air96_per_key.h").read_text()
        source = (ROOT / "firmware/keymaps/omarchy/air96_per_key.c").read_text()
        self.assertIn("#define AIR96_CMD_PROBE 0xA6", header)
        self.assertIn("#define AIR96_CMD_SET 0xA7", header)
        self.assertIn("#define AIR96_CMD_CLEAR 0xA8", header)
        self.assertIn("#define AIR96_CMD_MODS 0xA9", header)
        self.assertIn("#define AIR96_PER_KEY_TIMEOUT_MS 2000", header)
        self.assertIn("bool via_command_kb", source)
        self.assertNotIn("void via_command_kb", source)
        self.assertIn("raw_hid_send(data, length)", source)
        self.assertIn("return false;", source)
        self.assertIn("hypr_modmask", source)
        self.assertIn("MOD_MASK_GUI", source)
        self.assertNotIn("paint_super", source)
        self.assertNotIn("basic_key", source)

    def test_qmk_sends_via_replies_unless_the_keymap_claims_them(self):
        board = PerKeyController()
        version = board.exchange(protocol_version_request())
        self.assertEqual(version[0], 0x01)
        self.assertEqual(version[1:3], b"\x00\x0d")
        self.assertIsNone(board.exchange(protocol_version_request(), claim_without_sending=True))
        probe = board.exchange(per_key_probe_request())
        self.assertEqual(probe[:6], bytes((0xA6, ord("A"), ord("9"), ord("6"), ord("K"), 1)))
        lighting = board.exchange(lighting_get(VAL_EFFECT))
        self.assertEqual(len(lighting), 32)
        bad = bytearray(per_key_clear_request())
        bad[1] = 0
        self.assertEqual(board.exchange(bad)[0], 0xFF)

    def test_single_led_batch_and_short_probe(self):
        packets = per_key_set_packets([(9, 8, 7)], offset=38)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 0xA7)
        self.assertEqual(packets[0][1], 38)
        self.assertEqual(packets[0][2], 1)
        self.assertEqual(packets[0][3:6], bytes((9, 8, 7)))
        full = per_key_set_packets([(1, 2, 3)] * 110)
        self.assertEqual(len(full), 13)
        board = PerKeyController()
        ack = board.handle(packets[0])
        self.assertEqual(ack[0], 0xA7)
        self.assertEqual(board.colors[38], (9, 8, 7))
        short = bytes((0xA6, ord("A"), ord("9"), ord("6"), ord("K"), 1))
        self.assertTrue(per_key_supported(short))
        self.assertIsNone(per_key_capabilities(short)["leds"])

    def test_timeout_refresh_disconnect_and_clear(self):
        board = PerKeyController()
        probe = board.handle(per_key_probe_request())
        caps = per_key_capabilities(probe)
        self.assertEqual(caps["leds"], 100)
        self.assertEqual(caps["leds_per_packet"], 9)
        self.assertEqual(caps["timeout_ms"], 2000)
        self.assertFalse(board.active)
        board.handle(per_key_set_packets([(1, 2, 3)])[0])
        board.advance(1999)
        self.assertTrue(board.active)
        board.advance(2)
        self.assertFalse(board.active)
        board.handle(per_key_set_packets([(4, 5, 6)])[0])
        board.handle(per_key_probe_request())
        board.advance(1999)
        self.assertTrue(board.active)
        board.advance(2)
        self.assertFalse(board.active)
        board.handle(per_key_set_packets([(1, 1, 1)])[0])
        board.set_usb(False)
        self.assertFalse(board.active)
        ignored = board.handle(per_key_set_packets([(9, 9, 9)])[0])
        self.assertEqual(ignored[0], 0xA7)
        self.assertFalse(board.active)
        self.assertNotEqual(board.colors[0], (9, 9, 9))
        board.set_usb(True)
        board.handle(per_key_set_packets([(2, 0, 0)])[0])
        bad = bytearray(per_key_clear_request())
        bad[1] = 0
        self.assertEqual(board.handle(bad)[0], 0xFF)
        self.assertTrue(board.active)
        cleared = board.handle(per_key_clear_request())
        self.assertEqual(cleared[0], 0xA8)
        self.assertFalse(board.active)

    def test_side_indexes_are_acked_without_a_stored_color(self):
        board = PerKeyController()
        packet = per_key_set_packets([(9, 9, 9)] * 9, offset=100)[0]
        self.assertEqual(board.handle(packet)[0], 0xA7)
        self.assertEqual(board.colors, [(0, 0, 0)] * 100)
        self.assertTrue(board.active)

    def test_modifier_report_matches_hyprland_bits(self):
        board = PerKeyController()
        board.qmk_mods = 0x88 | 0x02  # left GUI + left Shift
        reply = board.exchange(per_key_mods_request())
        self.assertEqual(reply[0], 0xA9)
        self.assertEqual(parse_per_key_mods(reply), 64 | 1)
        board.qmk_mods = 0x88 | 0x02 | 0x44  # + Alt
        self.assertEqual(parse_per_key_mods(board.exchange(per_key_mods_request())), 64 | 1 | 8)
        board.qmk_mods = 0x11  # Ctrl only
        self.assertEqual(parse_per_key_mods(board.exchange(per_key_mods_request())), 4)
        bad = bytearray(per_key_mods_request())
        bad[1] = 0
        self.assertIsNone(parse_per_key_mods(board.exchange(bad)))

    def test_unchanged_music_frame_sends_no_led_packets(self):
        colors = [(0, 0, 0)] * 100
        self.assertEqual(per_key_delta_packets(colors, colors), [])
        moved = list(colors)
        moved[4] = (0, 0, 40)
        moved[5] = (0, 0, 4)  # under the change threshold
        packets = per_key_delta_packets(colors, moved)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][1], 4)
        self.assertEqual(packets[0][2], 1)
        self.assertEqual(packets[0][3:6], bytes((0, 0, 40)))


if __name__ == "__main__":
    unittest.main()
