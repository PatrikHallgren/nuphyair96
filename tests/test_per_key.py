import unittest

from air96_per_key import PerKeyController
from air96_protocol import (
    per_key_capabilities,
    per_key_clear_request,
    per_key_probe_request,
    per_key_set_packets,
    per_key_supported,
)
from support import ROOT


class PerKeyTests(unittest.TestCase):
    def test_firmware_header_matches_the_host_constants(self):
        header = (ROOT / "firmware/keymaps/omarchy/air96_per_key.h").read_text()
        source = (ROOT / "firmware/keymaps/omarchy/air96_per_key.c").read_text()
        self.assertIn("#define AIR96_CMD_PROBE 0xA6", header)
        self.assertIn("#define AIR96_CMD_SET 0xA7", header)
        self.assertIn("#define AIR96_CMD_CLEAR 0xA8", header)
        self.assertIn("#define AIR96_PER_KEY_TIMEOUT_MS 2000", header)
        self.assertIn("return true;", source)

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


if __name__ == "__main__":
    unittest.main()
