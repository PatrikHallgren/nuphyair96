"""Model of the Air96 per-key overlay implemented in the Omarchy keymap.

The C file ``firmware/keymaps/omarchy/air96_per_key.c`` uses the same command
bytes, the same 2000 ms timeout, and the same USB-unplug clear. Tests drive
this model. It does not open a keyboard.
"""

KEY_LEDS = 100
TIMEOUT_MS = 2000
LEDS_PER_PACKET = 9
FLAG_TIMEOUT = 0x01
FLAG_SUPER = 0x02  # no longer reported; the keymap does not paint a Super mask
FLAG_CLEAR = 0x04
FLAGS = FLAG_TIMEOUT | FLAG_CLEAR

# QMK modifier masks: left|right for shift, ctrl, alt, gui.
MOD_MASK_SHIFT = 0x22
MOD_MASK_CTRL = 0x11
MOD_MASK_ALT = 0x44
MOD_MASK_GUI = 0x88


def hypr_modmask(mods):
    """Same mapping as hypr_modmask() in the keymap."""
    mask = 0
    if mods & MOD_MASK_SHIFT:
        mask |= 1
    if mods & MOD_MASK_CTRL:
        mask |= 4
    if mods & MOD_MASK_ALT:
        mask |= 8
    if mods & MOD_MASK_GUI:
        mask |= 64
    return mask


class PerKeyController:
    def __init__(self):
        self.colors = [(0, 0, 0)] * KEY_LEDS
        self.active = False
        self.now = 0
        self.deadline = 0
        self.usb = True
        self.qmk_mods = 0

    def advance(self, ms):
        self.now += ms
        self._expire()

    def set_usb(self, connected):
        self.usb = bool(connected)
        if not self.usb:
            self.active = False

    def _expire(self):
        if self.active and self.now > self.deadline:
            self.active = False

    def _touch(self):
        self.active = True
        self.deadline = self.now + TIMEOUT_MS

    def handle(self, packet):
        data = bytearray(packet[:32])
        if len(data) < 32:
            data.extend(b"\x00" * (32 - len(data)))
        command = data[0]
        if command == 0xA6:
            return self._probe(data)
        if command == 0xA8:
            return self._clear(data)
        if command == 0xA7:
            return self._set(data)
        if command == 0xA9:
            return self._mods(data)
        data[0] = 0xFF
        return bytes(data)

    def via_command_kb(self, data):
        """The Omarchy keymap hook. True means raw_hid_send already ran."""
        if len(data) < 6 or data[0] not in (0xA6, 0xA7, 0xA8, 0xA9):
            return False
        reply = bytearray(self.handle(bytes(data)))
        if reply[0] == 0xFF:
            return False
        data[:] = reply
        return True

    def exchange(self, packet, claim_without_sending=False):
        """QMK raw_hid_receive from the pinned nuphy-qmk via.c.

        A true via_command_kb return skips QMK's raw_hid_send. The flashed
        keymap defined that function as void, so the caller treated a leftover
        register as true and no report came back.
        """
        data = bytearray(packet[:32])
        if len(data) < 32:
            data.extend(b"\x00" * (32 - len(data)))
        if claim_without_sending:
            return None
        if self.via_command_kb(data):
            return bytes(data)
        if data[0] == 0x01:
            data[1] = 0x00
            data[2] = 0x0D
        else:
            data[0] = 0xFF
        return bytes(data)

    def _probe(self, data):
        if bytes(data[1:5]) != b"A96K":
            data[0] = 0xFF
            return bytes(data)
        if data[5] == 0:
            self.active = False
        elif self.active and self.usb:
            self.deadline = self.now + TIMEOUT_MS
        data[0] = 0xA6
        data[1:5] = b"A96K"
        data[5] = 1
        data[6] = KEY_LEDS
        data[7] = LEDS_PER_PACKET
        data[8] = FLAGS
        data[9] = (TIMEOUT_MS >> 8) & 0xFF
        data[10] = TIMEOUT_MS & 0xFF
        return bytes(data)

    def _clear(self, data):
        if bytes(data[1:5]) != b"A96K":
            data[0] = 0xFF
            return bytes(data)
        self.active = False
        data[0] = 0xA8
        return bytes(data)

    def _set(self, data):
        count = data[2]
        offset = data[1]
        if count < 1 or count > LEDS_PER_PACKET or 3 + count * 3 > 32:
            data[0] = 0xFF
            return bytes(data)
        if self.usb:
            for index in range(count):
                led = offset + index
                if led >= KEY_LEDS:
                    continue
                base = 3 + index * 3
                self.colors[led] = (data[base], data[base + 1], data[base + 2])
            self._touch()
        else:
            self.active = False
        data[0] = 0xA7
        return bytes(data)

    def _mods(self, data):
        if bytes(data[1:5]) != b"A96K":
            data[0] = 0xFF
            return bytes(data)
        data[0] = 0xA9
        data[5] = hypr_modmask(self.qmk_mods)
        data[6] = self.qmk_mods & 0xFF
        return bytes(data)
