"""VIA raw-HID packets for the NuPhy Air96 V2.

The command bytes are QMK's VIA protocol version 0x000C as implemented in the
NuPhy fork (``quantum/via.h`` / ``quantum/via.c`` on ``nuphy-keyboards``):

* report size 32 (QMK ``RAW_EPSIZE``; the Air96 headers do not override it)
* no report ID in the raw-HID descriptor
* RGB matrix channel 3, which is what NuPhy's VIA JSON sends
* keymap cells are big-endian at
  ``(layer * rows * cols + row * cols + col) * 2``

Stock firmware has no per-key host command. ``0xA6`` / ``0xA7`` are a proposed
extension. Unhandled VIA commands are echoed with the command byte set to
``0xFF``, so a probe cannot reset the keyboard or jump to the bootloader.
"""

import colorsys

PACKET_SIZE = 32
BUFFER_CHUNK = 28

CMD_GET_PROTOCOL = 0x01
CMD_GET_KEYCODE = 0x04
CMD_SET_KEYCODE = 0x05
CMD_CUSTOM_SET = 0x07
CMD_CUSTOM_GET = 0x08
CMD_CUSTOM_SAVE = 0x09
CMD_GET_LAYER_COUNT = 0x11
CMD_GET_BUFFER = 0x12
CMD_UNHANDLED = 0xFF

CHANNEL_RGB_MATRIX = 3
VAL_BRIGHTNESS = 1
VAL_EFFECT = 2
VAL_SPEED = 3
VAL_COLOR = 4

# Proposed, not implemented by stock firmware. See docs/PER-KEY.md.
CMD_PER_KEY_PROBE = 0xA6
CMD_PER_KEY_SET = 0xA7
PER_KEY_MAGIC = b"A96K"
PER_KEY_VERSION = 1
PER_KEY_LEDS_PER_PACKET = 9

# Dropdown order from "NuPhy Air96 V2 via3.json" shipped in the firmware tree.
# Index 0 disables the matrix. Index 1 is solid color. Names are NuPhy's.
EFFECTS = (
    "All Off",
    "Solid Color",
    "Gradient Up/Down",
    "Gradient Left/Right",
    "Breathing",
    "Band Sat.",
    "Band Val.",
    "Pinwheel Sat.",
    "Pinwheel Val.",
    "Spiral Sat.",
    "Spiral Val.",
    "Cycle All",
    "Cycle Left/Right",
    "Cycle Up/Down",
    "Rainbow Moving Chevron",
    "Cycle Out/In",
    "Cycle Out/In Dual",
    "Cycle Pinwheel",
    "Cycle Spiral",
    "Dual Beacon",
    "Rainbow Beacon",
    "Rainbow Pinwheels",
    "Raindrops",
    "Jellybean Raindrops",
    "Hue Breathing",
    "Hue Pendulum",
    "Hue Wave",
    "Typing Heatmap",
    "Digital Rain",
    "Reactive Simple",
    "Reactive",
    "Reactive Wide",
    "Reactive Multiwide",
    "Reactive Cross",
    "Reactive Multicross",
    "Reactive Nexus",
    "Reactive MultiNexus",
    "Splash",
    "MultiSplash",
    "Solid Splash",
    "Solid MultiSplash",
)

SOLID_EFFECT = 1


class ProtocolError(ValueError):
    pass


def packet(values):
    if len(values) > PACKET_SIZE:
        raise ProtocolError("VIA packet longer than 32 bytes")
    data = bytearray(PACKET_SIZE)
    for index, value in enumerate(values):
        data[index] = int(value) & 0xFF
    return bytes(data)


def protocol_version_request():
    return packet((CMD_GET_PROTOCOL,))


def parse_protocol_version(response):
    if len(response) < 3 or response[0] == CMD_UNHANDLED:
        raise ProtocolError("Keyboard did not answer the VIA version query")
    if response[0] != CMD_GET_PROTOCOL:
        raise ProtocolError("Unexpected response to the VIA version query")
    return (response[1] << 8) | response[2]


def lighting_get(value_id):
    return packet((CMD_CUSTOM_GET, CHANNEL_RGB_MATRIX, value_id))


def lighting_set(value_id, *data):
    return packet((CMD_CUSTOM_SET, CHANNEL_RGB_MATRIX, value_id, *data))


def lighting_save():
    return packet((CMD_CUSTOM_SAVE, CHANNEL_RGB_MATRIX))


def parse_lighting_get(response, value_id):
    if len(response) < 4 or response[0] == CMD_UNHANDLED:
        raise ProtocolError("Keyboard rejected the lighting read")
    if response[0] != CMD_CUSTOM_GET or response[1] != CHANNEL_RGB_MATRIX or response[2] != value_id:
        raise ProtocolError("Unexpected lighting read response")
    if value_id == VAL_COLOR:
        return (response[3], response[4] if len(response) > 4 else 0)
    return response[3]


def layer_count_request():
    return packet((CMD_GET_LAYER_COUNT,))


def parse_layer_count(response):
    if len(response) < 2 or response[0] != CMD_GET_LAYER_COUNT:
        raise ProtocolError("Keyboard rejected the layer-count read")
    count = response[1]
    if not 1 <= count <= 32:
        raise ProtocolError("Implausible VIA layer count")
    return count


def buffer_request(offset, size):
    if not 0 <= offset <= 0xFFFF or not 1 <= size <= BUFFER_CHUNK:
        raise ProtocolError("Invalid keymap buffer read")
    return packet((CMD_GET_BUFFER, (offset >> 8) & 0xFF, offset & 0xFF, size))


def parse_buffer(response, offset, size):
    if len(response) < 4 + size or response[0] != CMD_GET_BUFFER:
        raise ProtocolError("Keyboard rejected the keymap read")
    if response[1] != ((offset >> 8) & 0xFF) or response[2] != (offset & 0xFF) or response[3] != size:
        raise ProtocolError("Keymap read returned a different range")
    return bytes(response[4:4 + size])


def set_keycode_request(layer, row, col, keycode):
    if not 0 <= keycode <= 0xFFFF:
        raise ProtocolError("Keycode out of range")
    return packet((CMD_SET_KEYCODE, layer, row, col, (keycode >> 8) & 0xFF, keycode & 0xFF))


def get_keycode_request(layer, row, col):
    return packet((CMD_GET_KEYCODE, layer, row, col))


def parse_keycode(response, layer, row, col):
    if len(response) < 6 or response[0] != CMD_GET_KEYCODE:
        raise ProtocolError("Keyboard rejected the keycode read")
    if response[1] != layer or response[2] != row or response[3] != col:
        raise ProtocolError("Keycode read returned a different key")
    return (response[4] << 8) | response[5]


def keymap_offset(layer, row, col, rows, cols):
    return (layer * rows * cols + row * cols + col) * 2


def keymap_size(layers, rows, cols):
    return layers * rows * cols * 2


def per_key_probe_request():
    return packet((CMD_PER_KEY_PROBE, *PER_KEY_MAGIC, PER_KEY_VERSION))


def per_key_supported(response):
    """True only for the proposed firmware ack. Stock VIA returns 0xFF."""
    if len(response) < 6 or response[0] != CMD_PER_KEY_PROBE:
        return False
    return bytes(response[1:5]) == PER_KEY_MAGIC and response[5] == PER_KEY_VERSION


def per_key_set_packets(colors):
    """Build direct-color packets. ``colors`` is a list of (r, g, b)."""
    packets = []
    offset = 0
    while offset < len(colors):
        chunk = list(colors[offset:offset + PER_KEY_LEDS_PER_PACKET])
        values = [CMD_PER_KEY_SET, offset & 0xFF, len(chunk)]
        for red, green, blue in chunk:
            values.extend((int(red) & 0xFF, int(green) & 0xFF, int(blue) & 0xFF))
        packets.append(packet(values))
        offset += len(chunk)
    return packets


def effect_name(index):
    if 0 <= index < len(EFFECTS):
        return EFFECTS[index]
    return f"Effect {index}"


def normalize_hex(text):
    if not isinstance(text, str):
        return ""
    raw = text.strip().lower()
    if raw.startswith("#"):
        raw = raw[1:]
    if raw.startswith("0x"):
        raw = raw[2:]
    if len(raw) == 8 and raw.startswith("ff"):  # ignore a leading opaque alpha
        raw = raw[2:]
    if len(raw) != 6 or any(ch not in "0123456789abcdef" for ch in raw):
        return ""
    return "#" + raw


def hex_to_rgb(text):
    color = normalize_hex(text)
    if not color:
        raise ProtocolError("Color must be #RRGGBB")
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_qmk_hsv(red, green, blue):
    """Hue/sat/val on QMK's 0-255 scale.

    VIA's color command stores hue and saturation and leaves brightness alone.
    QMK's own ``hsv_to_rgb`` uses integer regions (``h * 6 / 255``), so a
    colorsys conversion is close for theme accents rather than bit-exact.
    """
    hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    return round(hue * 255) % 256, round(sat * 255), round(val * 255)


def hex_to_qmk_hs(text):
    red, green, blue = hex_to_rgb(text)
    hue, sat, _val = rgb_to_qmk_hsv(red, green, blue)
    return hue, sat
