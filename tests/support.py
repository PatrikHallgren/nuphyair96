import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from air96_backend import Backend  # noqa: E402
from air96_layout import MATRIX_COLS, MATRIX_ROWS  # noqa: E402


class FakeKeyboard:
    """Enough of VIA for the Air96 to exercise the backend without hidraw."""

    def __init__(self, per_key=False):
        self.effect = 1
        self.brightness = 80
        self.speed = 40
        self.hue = 10
        self.sat = 20
        self.saved = 0
        self.layers = 8
        self.per_key = per_key
        self.frames = []
        self.commands = []
        self.hypr_mods = 0
        self.colors = [(0, 0, 0)] * 110
        self.blob = bytearray(self.layers * MATRIX_ROWS * MATRIX_COLS * 2)
        self.blob[1] = 0x04  # layer 0, row 0, col 0 = KC_A

    def transact(self, payload):
        data = bytearray(payload)
        command = data[0]
        self.commands.append(command)
        if command == 0x01:
            data[1] = 0x00
            data[2] = 0x0C
        elif command == 0x08:
            value = data[2]
            if value == 1:
                data[3] = self.brightness
            elif value == 2:
                data[3] = self.effect
            elif value == 3:
                data[3] = self.speed
            elif value == 4:
                data[3] = self.hue
                data[4] = self.sat
        elif command == 0x07:
            value = data[2]
            if value == 1:
                self.brightness = data[3]
            elif value == 2:
                self.effect = data[3]
            elif value == 3:
                self.speed = data[3]
            elif value == 4:
                self.hue = data[3]
                self.sat = data[4]
        elif command == 0x09:
            self.saved += 1
        elif command == 0x11:
            data[1] = self.layers
        elif command == 0x12:
            offset = (data[1] << 8) | data[2]
            size = data[3]
            data[4:4 + size] = self.blob[offset:offset + size]
        elif command == 0x04:
            offset = self._offset(data[1], data[2], data[3])
            data[4] = self.blob[offset]
            data[5] = self.blob[offset + 1]
        elif command == 0x05:
            offset = self._offset(data[1], data[2], data[3])
            self.blob[offset] = data[4]
            self.blob[offset + 1] = data[5]
        elif command == 0xA6:
            if self.per_key:
                data[1:5] = b"A96K"
                data[5] = 1
                data[6] = 100
                data[7] = 9
                data[8] = 0x05
                data[9] = (2000 >> 8) & 0xFF
                data[10] = 2000 & 0xFF
            else:
                data[0] = 0xFF
        elif command == 0xA7:
            if self.per_key:
                self.frames.append(bytes(data))
                offset = data[1]
                count = data[2]
                for index in range(count):
                    led = offset + index
                    base = 3 + index * 3
                    if led < len(self.colors) and base + 2 < len(data):
                        self.colors[led] = (data[base], data[base + 1], data[base + 2])
            else:
                data[0] = 0xFF
        elif command == 0xA8:
            if self.per_key and bytes(data[1:5]) == b"A96K":
                data[0] = 0xA8
            else:
                data[0] = 0xFF
        elif command == 0xA9:
            if self.per_key and bytes(data[1:5]) == b"A96K":
                data[0] = 0xA9
                data[5] = self.hypr_mods & 0xFF
            else:
                data[0] = 0xFF
        else:
            data[0] = 0xFF
        return bytes(data)

    def _offset(self, layer, row, col):
        return (layer * MATRIX_ROWS * MATRIX_COLS + row * MATRIX_COLS + col) * 2

    def keycode(self, layer, row, col):
        offset = self._offset(layer, row, col)
        return (self.blob[offset] << 8) | self.blob[offset + 1]


class BackendCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.theme = root / "theme"
        self.theme.mkdir()
        self.backend = Backend(
            config_path=root / "config.json",
            state_dir=root / "state",
            theme_path=self.theme,
            profiles_dir=root / "profiles",
            environ={},
        )
        self.keyboard = FakeKeyboard()

    def tearDown(self):
        self.temp.cleanup()

    def connect(self, per_key=False):
        self.keyboard = FakeKeyboard(per_key=per_key)
        self.backend.set_device(
            {"path": "/dev/hidraw9", "vid": 0x19F5, "pid": 0x3265, "name": "NuPhy Air96 V2", "iface": 1},
            self.keyboard,
            "",
        )


if __name__ == "__main__":
    unittest.main()
