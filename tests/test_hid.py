import os
import unittest
from pathlib import Path

import support  # noqa: F401
from air96_hid import application_usages, find_devices


def descriptor(page, usage, wide_page=False):
    if wide_page:
        page_item = bytes((0x06, page & 0xFF, (page >> 8) & 0xFF))
    else:
        page_item = bytes((0x05, page & 0xFF))
    return page_item + bytes((0x09, usage, 0xA1, 0x01, 0xC0))


class HidDiscoveryTests(unittest.TestCase):
    def test_usage_parser_finds_via(self):
        self.assertEqual(application_usages(descriptor(0xFF60, 0x61, wide_page=True)), [(0xFF60, 0x61)])
        self.assertEqual(application_usages(descriptor(0x01, 0x06)), [(0x01, 0x06)])

    def test_only_the_raw_interface_of_known_pids_matches(self):
        root = Path(self.id().replace(".", "_"))
        # TemporaryDirectory keeps the tree for the duration of the test.
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self._node(base, "hidraw0", 0x3265, descriptor(0xFF60, 0x61, wide_page=True), "NuPhy Air96 V2")
            self._node(base, "hidraw1", 0x3265, descriptor(0x01, 0x06), "NuPhy Air96 V2 Keyboard")
            self._node(base, "hidraw2", 0x3266, descriptor(0xFF60, 0x61, wide_page=True), "NuPhy Air96 V2")
            self._node(base, "hidraw3", 0x1028, descriptor(0xFF60, 0x61, wide_page=True), "NuPhy Air75 V3")
            found = find_devices(base)
            pids = sorted(device["pid"] for device in found)
            self.assertEqual(pids, [0x3265, 0x3266])
            self.assertTrue(all(device["name"].startswith("NuPhy Air96") for device in found))

    def _node(self, base, name, pid, report, product):
        device = base / name / "device"
        device.mkdir(parents=True)
        (device / "uevent").write_text(f"HID_ID=0003:000019F5:{pid:08X}\nHID_NAME={product}\n")
        (device / "report_descriptor").write_bytes(report)
        os.symlink(device, base / name / "device-link")


if __name__ == "__main__":
    unittest.main()
