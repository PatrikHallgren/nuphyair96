# Air96 V2 protocol

This plugin talks to the keyboard with QMK VIA raw HID. It does not use `nuphyctl` or the NuPhy IO session used by newer boards such as the Air75 V3.

Sources, read while writing this plugin:

- NuPhy QMK fork, branch `nuphy-keyboards`, keyboard `keyboards/nuphy/air96_v2/ansi` (`keyboard.json`, `config.h`, `ansi.c`, `side.c`, the VIA keymap and `NuPhy Air96 V2 via3.json`).
- QMK `quantum/via.h` and `quantum/via.c` in that same tree (protocol version `0x000C`).
- Community reports that firmware generation 2.1.x enumerates as product id `0x3265` while the JSON still says `0x3266`.

## Identity

| Field | Value |
| --- | --- |
| Vendor | `0x19F5` |
| Product | `0x3266` in the official JSON, and `0x3265` on reported 2.1.x firmware |
| Raw HID | usage page `0xFF60`, usage `0x61` |
| Report | 32 bytes, no report ID |
| Matrix | 6 rows × 21 columns, column-to-row |
| Layers | 8 in EEPROM. Stock keymap defines 0 Mac, 1 Mac Fn, 2 Windows, 3 Windows Fn, 4 Function |
| LEDs | 110. Indexes 0–99 are keys in `rgb_matrix.layout` order. 100–104 left side, 105–109 right side |

Control requires the USB cable. Bluetooth and the 2.4G dongle do not expose this raw HID interface. A dongle may also use a different product id; this plugin does not match every `0x19F5` device.

Some hosts reject a write that has no report ID. On `EINVAL` the transport retries the same 32 bytes with a leading `0x00`. A 33-byte read with a leading zero is stripped.

## Lighting

VIA channel 3, from NuPhy's VIA JSON:

| Value id | Meaning |
| --- | --- |
| 1 | brightness 0–255 |
| 2 | effect index |
| 3 | speed 0–255 |
| 4 | color, hue and saturation, each 0–255 |

Effect 0 is All Off. Effect 1 is Solid Color. The other names are the VIA JSON dropdown, indexes 2–40. A later firmware can shift those indexes. The UI shows the numeric mode when the name is unknown, and readback uses the number the keyboard returns.

QMK hue is 0–255, not 0–360. The color command does not carry brightness. White is saturation 0. `colorsys` is close to QMK's integer `hsv_to_rgb`, not bit-exact. Firmware `scale8(brightness, 255)` is one step under the byte you send (255 becomes 254).

Set commands are not stored until custom-save `0x09`. This plugin saves after a successful lighting apply. It never sends VIA `0x0A` (EEPROM reset) or `0x0B` (bootloader).

Side LEDs are driven by `SIDE_*` keycodes in `side.c`. VIA lighting does not address them.

## Keymap

Cell offset `(layer * 6 * 21 + row * 21 + col) * 2`, big-endian keycode. The buffer is 2016 bytes, read 28 bytes at a time with command `0x12`. Set one cell with `0x05`. Get one cell with `0x04`.

`KC_TRANSPARENT` is 1. `KC_NO` is 0. `MO(n)` is `0x5220 | n`.

The published keymap uses names such as `RGB_MOD` that, in upstream QMK, are underglow keycodes rather than RGB-matrix keycodes. The flashed 2.1 binary may differ. The plugin displays the value the keyboard returns and does not rewrite those keys.

## Per-key

Stock `via.c` answers an unknown command by echoing it with byte 0 set to `0xFF`. Probing `0xA6` is safe on that firmware. There is no stock command that sets one LED. Effects and `side.c` repaint every frame, so a one-shot color would not stick even if a command existed.

The proposed extension is in [PER-KEY.md](PER-KEY.md). On-screen highlights do not need it.
