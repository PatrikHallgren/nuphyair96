"""Air96 V2 physical layout, matrix coordinates, and RGB indexes.

Transcribed from NuPhy's QMK ``keyboard.json`` (100 keys, then 10 side LEDs):

https://github.com/nuphy-src/qmk_firmware/blob/nuphy-keyboards/keyboards/nuphy/air96_v2/ansi/keyboard.json

LED index ``i`` is the ``rgb_matrix.layout`` order. Indexes 0-99 are keys.
Indexes 100-109 are the side strips (``SIDE_INDEX`` in ``side.c``): 100-104 left,
105-109 right. ``RGB_MATRIX_LED_COUNT`` is 110 (58 + 42 + 10).

Matrix is 6 rows by 21 columns. VIA dynamic keymaps address every cell, including
positions with no keycap.
"""

MATRIX_ROWS = 6
MATRIX_COLS = 21
LAYER_COUNT = 8
LED_COUNT = 110
KEY_LED_COUNT = 100
SIDE_LED_START = 100
SIDE_LED_COUNT = 10
# side.c set_left_rgb writes SIDE_INDEX+0..4; set_right_rgb writes +5..9.
LEFT_SIDE_LEDS = (100, 101, 102, 103, 104)
RIGHT_SIDE_LEDS = (105, 106, 107, 108, 109)

# Stock keymap.c labels layers 0-4. VIA layer_count is 8, so 5-7 exist in EEPROM
# even though the published keymap does not define them.
LAYERS = (
    {"id": 0, "name": "Mac"},
    {"id": 1, "name": "Mac Fn"},
    {"id": 2, "name": "Windows"},
    {"id": 3, "name": "Windows Fn"},
    {"id": 4, "name": "Function"},
    {"id": 5, "name": "Layer 5"},
    {"id": 6, "name": "Layer 6"},
    {"id": 7, "name": "Layer 7"},
)

# USB IDs. keyboard.json and the bundled VIA JSON say pid 0x3266 (device version
# 1.1.8). Boards on the later QMK 2.1.x firmware have been reported as pid 0x3265
# while the official JSON still said 0x3266. Accept both. Vendor is NuPhy 0x19F5.
VENDOR_ID = 0x19F5
PRODUCT_IDS = (0x3265, 0x3266)
# QMK raw HID / VIA. Not overridden in the Air96 config headers.
VIA_USAGE_PAGE = 0xFF60
VIA_USAGE = 0x61

KEYS = [
  {
    "id": "esc",
    "label": "Esc",
    "row": 0,
    "col": 0,
    "x": 0,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 0
  },
  {
    "id": "f1",
    "label": "F1",
    "row": 0,
    "col": 2,
    "x": 1,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 1
  },
  {
    "id": "f2",
    "label": "F2",
    "row": 0,
    "col": 3,
    "x": 2,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 2
  },
  {
    "id": "f3",
    "label": "F3",
    "row": 0,
    "col": 4,
    "x": 3,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 3
  },
  {
    "id": "f4",
    "label": "F4",
    "row": 0,
    "col": 5,
    "x": 4,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 4
  },
  {
    "id": "f5",
    "label": "F5",
    "row": 0,
    "col": 6,
    "x": 5,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 5
  },
  {
    "id": "f6",
    "label": "F6",
    "row": 0,
    "col": 7,
    "x": 6,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 6
  },
  {
    "id": "f7",
    "label": "F7",
    "row": 0,
    "col": 8,
    "x": 7,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 7
  },
  {
    "id": "f8",
    "label": "F8",
    "row": 0,
    "col": 9,
    "x": 8,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 8
  },
  {
    "id": "f9",
    "label": "F9",
    "row": 0,
    "col": 10,
    "x": 9,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 9
  },
  {
    "id": "f10",
    "label": "F10",
    "row": 0,
    "col": 11,
    "x": 10,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 10
  },
  {
    "id": "f11",
    "label": "F11",
    "row": 0,
    "col": 12,
    "x": 11,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 11
  },
  {
    "id": "f12",
    "label": "F12",
    "row": 0,
    "col": 13,
    "x": 12,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 12
  },
  {
    "id": "print",
    "label": "Print",
    "row": 0,
    "col": 14,
    "x": 13,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 13
  },
  {
    "id": "delete",
    "label": "Del",
    "row": 2,
    "col": 14,
    "x": 14,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 14
  },
  {
    "id": "home",
    "label": "Home",
    "row": 1,
    "col": 15,
    "x": 15,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 15
  },
  {
    "id": "end",
    "label": "End",
    "row": 2,
    "col": 15,
    "x": 16,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 16
  },
  {
    "id": "pageup",
    "label": "PageUp",
    "row": 1,
    "col": 16,
    "x": 17,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 17
  },
  {
    "id": "pagedown",
    "label": "PageDn",
    "row": 2,
    "col": 16,
    "x": 18,
    "y": 0,
    "w": 1,
    "h": 1,
    "led": 18
  },
  {
    "id": "grave",
    "label": "~`",
    "row": 1,
    "col": 0,
    "x": 0,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 19
  },
  {
    "id": "1",
    "label": "!1",
    "row": 1,
    "col": 1,
    "x": 1,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 20
  },
  {
    "id": "2",
    "label": "@2",
    "row": 1,
    "col": 2,
    "x": 2,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 21
  },
  {
    "id": "3",
    "label": "#3",
    "row": 1,
    "col": 3,
    "x": 3,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 22
  },
  {
    "id": "4",
    "label": "$4",
    "row": 1,
    "col": 4,
    "x": 4,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 23
  },
  {
    "id": "5",
    "label": "%5",
    "row": 1,
    "col": 5,
    "x": 5,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 24
  },
  {
    "id": "6",
    "label": "^6",
    "row": 1,
    "col": 6,
    "x": 6,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 25
  },
  {
    "id": "7",
    "label": "&7",
    "row": 1,
    "col": 7,
    "x": 7,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 26
  },
  {
    "id": "8",
    "label": "*8",
    "row": 1,
    "col": 8,
    "x": 8,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 27
  },
  {
    "id": "9",
    "label": "(9",
    "row": 1,
    "col": 9,
    "x": 9,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 28
  },
  {
    "id": "0",
    "label": ")0",
    "row": 1,
    "col": 10,
    "x": 10,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 29
  },
  {
    "id": "minus",
    "label": "_-",
    "row": 1,
    "col": 11,
    "x": 11,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 30
  },
  {
    "id": "equal",
    "label": "+=",
    "row": 1,
    "col": 12,
    "x": 12,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 31
  },
  {
    "id": "backspace",
    "label": "Backsp",
    "row": 1,
    "col": 13,
    "x": 13,
    "y": 1,
    "w": 2,
    "h": 1,
    "led": 32
  },
  {
    "id": "num",
    "label": "Num",
    "row": 1,
    "col": 17,
    "x": 15,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 33
  },
  {
    "id": "kp_slash",
    "label": "/",
    "row": 1,
    "col": 18,
    "x": 16,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 34
  },
  {
    "id": "kp_asterisk",
    "label": "*",
    "row": 1,
    "col": 19,
    "x": 17,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 35
  },
  {
    "id": "kp_minus",
    "label": "-",
    "row": 1,
    "col": 20,
    "x": 18,
    "y": 1,
    "w": 1,
    "h": 1,
    "led": 36
  },
  {
    "id": "tab",
    "label": "Tab",
    "row": 2,
    "col": 0,
    "x": 0,
    "y": 2,
    "w": 1.5,
    "h": 1,
    "led": 37
  },
  {
    "id": "q",
    "label": "Q",
    "row": 2,
    "col": 1,
    "x": 1.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 38
  },
  {
    "id": "w",
    "label": "W",
    "row": 2,
    "col": 2,
    "x": 2.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 39
  },
  {
    "id": "e",
    "label": "E",
    "row": 2,
    "col": 3,
    "x": 3.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 40
  },
  {
    "id": "r",
    "label": "R",
    "row": 2,
    "col": 4,
    "x": 4.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 41
  },
  {
    "id": "t",
    "label": "T",
    "row": 2,
    "col": 5,
    "x": 5.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 42
  },
  {
    "id": "y",
    "label": "Y",
    "row": 2,
    "col": 6,
    "x": 6.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 43
  },
  {
    "id": "u",
    "label": "U",
    "row": 2,
    "col": 7,
    "x": 7.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 44
  },
  {
    "id": "i",
    "label": "I",
    "row": 2,
    "col": 8,
    "x": 8.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 45
  },
  {
    "id": "o",
    "label": "O",
    "row": 2,
    "col": 9,
    "x": 9.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 46
  },
  {
    "id": "p",
    "label": "P",
    "row": 2,
    "col": 10,
    "x": 10.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 47
  },
  {
    "id": "lbracket",
    "label": "{[",
    "row": 2,
    "col": 11,
    "x": 11.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 48
  },
  {
    "id": "rbracket",
    "label": "}]",
    "row": 2,
    "col": 12,
    "x": 12.5,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 49
  },
  {
    "id": "backslash",
    "label": "|\\",
    "row": 2,
    "col": 13,
    "x": 13.5,
    "y": 2,
    "w": 1.5,
    "h": 1,
    "led": 50
  },
  {
    "id": "kp7",
    "label": "7",
    "row": 2,
    "col": 17,
    "x": 15,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 51
  },
  {
    "id": "kp8",
    "label": "8",
    "row": 2,
    "col": 18,
    "x": 16,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 52
  },
  {
    "id": "kp9",
    "label": "9",
    "row": 2,
    "col": 19,
    "x": 17,
    "y": 2,
    "w": 1,
    "h": 1,
    "led": 53
  },
  {
    "id": "kp_plus",
    "label": "+",
    "row": 2,
    "col": 20,
    "x": 18,
    "y": 2,
    "w": 1,
    "h": 2,
    "led": 54
  },
  {
    "id": "caps",
    "label": "Caps",
    "row": 3,
    "col": 0,
    "x": 0,
    "y": 3,
    "w": 1.75,
    "h": 1,
    "led": 55
  },
  {
    "id": "a",
    "label": "A",
    "row": 3,
    "col": 1,
    "x": 1.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 56
  },
  {
    "id": "s",
    "label": "S",
    "row": 3,
    "col": 2,
    "x": 2.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 57
  },
  {
    "id": "d",
    "label": "D",
    "row": 3,
    "col": 3,
    "x": 3.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 58
  },
  {
    "id": "f",
    "label": "F",
    "row": 3,
    "col": 4,
    "x": 4.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 59
  },
  {
    "id": "g",
    "label": "G",
    "row": 3,
    "col": 5,
    "x": 5.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 60
  },
  {
    "id": "h",
    "label": "H",
    "row": 3,
    "col": 6,
    "x": 6.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 61
  },
  {
    "id": "j",
    "label": "J",
    "row": 3,
    "col": 7,
    "x": 7.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 62
  },
  {
    "id": "k",
    "label": "K",
    "row": 3,
    "col": 8,
    "x": 8.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 63
  },
  {
    "id": "l",
    "label": "L",
    "row": 3,
    "col": 9,
    "x": 9.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 64
  },
  {
    "id": "semicolon",
    "label": ":",
    "row": 3,
    "col": 10,
    "x": 10.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 65
  },
  {
    "id": "quote",
    "label": "\"",
    "row": 3,
    "col": 11,
    "x": 11.75,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 66
  },
  {
    "id": "enter",
    "label": "Enter",
    "row": 3,
    "col": 13,
    "x": 12.75,
    "y": 3,
    "w": 2.25,
    "h": 1,
    "led": 67
  },
  {
    "id": "kp4",
    "label": "4",
    "row": 3,
    "col": 17,
    "x": 15,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 68
  },
  {
    "id": "kp5",
    "label": "5",
    "row": 3,
    "col": 18,
    "x": 16,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 69
  },
  {
    "id": "kp6",
    "label": "6",
    "row": 3,
    "col": 19,
    "x": 17,
    "y": 3,
    "w": 1,
    "h": 1,
    "led": 70
  },
  {
    "id": "lshift",
    "label": "Shift",
    "row": 4,
    "col": 0,
    "x": 0,
    "y": 4,
    "w": 2.25,
    "h": 1,
    "led": 71
  },
  {
    "id": "z",
    "label": "Z",
    "row": 4,
    "col": 2,
    "x": 2.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 72
  },
  {
    "id": "x",
    "label": "X",
    "row": 4,
    "col": 3,
    "x": 3.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 73
  },
  {
    "id": "c",
    "label": "C",
    "row": 4,
    "col": 4,
    "x": 4.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 74
  },
  {
    "id": "v",
    "label": "V",
    "row": 4,
    "col": 5,
    "x": 5.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 75
  },
  {
    "id": "b",
    "label": "B",
    "row": 4,
    "col": 6,
    "x": 6.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 76
  },
  {
    "id": "n",
    "label": "N",
    "row": 4,
    "col": 7,
    "x": 7.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 77
  },
  {
    "id": "m",
    "label": "M",
    "row": 4,
    "col": 8,
    "x": 8.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 78
  },
  {
    "id": "comma",
    "label": "<,",
    "row": 4,
    "col": 9,
    "x": 9.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 79
  },
  {
    "id": "dot",
    "label": ">.",
    "row": 4,
    "col": 10,
    "x": 10.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 80
  },
  {
    "id": "slash",
    "label": "?/",
    "row": 4,
    "col": 11,
    "x": 11.25,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 81
  },
  {
    "id": "rshift",
    "label": "Shift",
    "row": 4,
    "col": 13,
    "x": 12.25,
    "y": 4,
    "w": 1.75,
    "h": 1,
    "led": 82
  },
  {
    "id": "up",
    "label": "\u2191",
    "row": 4,
    "col": 15,
    "x": 14,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 83
  },
  {
    "id": "kp1",
    "label": "1",
    "row": 4,
    "col": 17,
    "x": 15,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 84
  },
  {
    "id": "kp2",
    "label": "2",
    "row": 4,
    "col": 18,
    "x": 16,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 85
  },
  {
    "id": "kp3",
    "label": "3",
    "row": 4,
    "col": 19,
    "x": 17,
    "y": 4,
    "w": 1,
    "h": 1,
    "led": 86
  },
  {
    "id": "kp_enter",
    "label": "Enter",
    "row": 4,
    "col": 20,
    "x": 18,
    "y": 4,
    "w": 1,
    "h": 2,
    "led": 87
  },
  {
    "id": "lctrl",
    "label": "Ctrl",
    "row": 5,
    "col": 0,
    "x": 0,
    "y": 5,
    "w": 1.25,
    "h": 1,
    "led": 88
  },
  {
    "id": "lalt",
    "label": "Opt",
    "row": 5,
    "col": 1,
    "x": 1.25,
    "y": 5,
    "w": 1.25,
    "h": 1,
    "led": 89
  },
  {
    "id": "lgui",
    "label": "Cmd",
    "row": 5,
    "col": 2,
    "x": 2.5,
    "y": 5,
    "w": 1.25,
    "h": 1,
    "led": 90
  },
  {
    "id": "space",
    "label": "Space",
    "row": 5,
    "col": 6,
    "x": 3.75,
    "y": 5,
    "w": 6.25,
    "h": 1,
    "led": 91
  },
  {
    "id": "rgui",
    "label": "Cmd",
    "row": 5,
    "col": 9,
    "x": 10,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 92
  },
  {
    "id": "fn",
    "label": "Fn",
    "row": 5,
    "col": 10,
    "x": 11,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 93
  },
  {
    "id": "rctrl",
    "label": "Ctrl",
    "row": 5,
    "col": 13,
    "x": 12,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 94
  },
  {
    "id": "left",
    "label": "\u2190",
    "row": 5,
    "col": 14,
    "x": 13,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 95
  },
  {
    "id": "down",
    "label": "\u2193",
    "row": 5,
    "col": 15,
    "x": 14,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 96
  },
  {
    "id": "right",
    "label": "\u2192",
    "row": 5,
    "col": 16,
    "x": 15,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 97
  },
  {
    "id": "kp0",
    "label": "0",
    "row": 5,
    "col": 17,
    "x": 16,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 98
  },
  {
    "id": "kp_dot",
    "label": ".",
    "row": 5,
    "col": 19,
    "x": 17,
    "y": 5,
    "w": 1,
    "h": 1,
    "led": 99
  }
]


def key_by_id(key_id):
    for key in KEYS:
        if key["id"] == key_id:
            return key
    return None


def key_by_matrix(row, col):
    for key in KEYS:
        if key["row"] == row and key["col"] == col:
            return key
    return None


def led_for_matrix(row, col):
    key = key_by_matrix(row, col)
    return None if key is None else key["led"]
