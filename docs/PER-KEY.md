# Per-key lighting

Stock Air96 V2 firmware (official 2.1.5) cannot show a host-chosen color on one key.

- VIA RGB channel 3 sets one effect, one hue, one saturation, one brightness, and one speed for the whole matrix.
- `side.c` owns LEDs 100–109 and only changes them for `SIDE_*` keycodes.
- The effect task overwrites key colors every frame.

The on-screen keyboard in the bar panel works on that firmware. The Omarchy keymap in [firmware/](../firmware/) adds a raw HID overlay the plugin can drive. USB only. Bluetooth and the 2.4G dongle do not expose the interface.

`per_key.push_to_keyboard` defaults to on. The worker still probes first. A stock board answers `0xFF` and the plugin leaves the matrix effect alone. A board that acknowledges the probe receives highlight frames, resent about once a second so the 2 second firmware timeout does not drop them. Turning the push off sends `0xA8` and reapplies the VIA effect.

Do not EEPROM-save these frames. They are a live overlay. The plugin's music mode uses the same packets and, on stock firmware, pulses global brightness and hue without saving.

## Probe, write, clear

All three are 32-byte reports. The batch layout (index, count, up to 9 RGB triples) matches the streaming packets in ravila4/nuphy-rgb-music. The command bytes stay `0xA6` / `0xA7` / `0xA8` so the existing probe does not change. That project targets the Air75 V2.

Probe `0xA6`:

| Bytes | Content |
| --- | --- |
| 0 | `0xA6` |
| 1–4 | ASCII `A96K` |
| 5 | version `1` to query, or `0` to clear |

Stock firmware: byte 0 comes back `0xFF`. The Omarchy keymap: byte 0 is `0xA6`, bytes 1–4 are `A96K`, byte 5 is `1`. A short ack is enough for the plugin to treat the board as capable. The current keymap also returns:

| Bytes | Content |
| --- | --- |
| 6 | paintable LED count, `100` |
| 7 | LEDs per packet, `9` |
| 8 | flags: bit 0 timeout, bit 1 Super fallback, bit 2 clear command |
| 9–10 | timeout in milliseconds, big-endian `2000` |

Set `0xA7`:

| Bytes | Content |
| --- | --- |
| 0 | `0xA7` |
| 1 | first LED index |
| 2 | count, 1–9 |
| 3–29 | RGB triples |

Count 1 is the single-LED command. Nine LEDs fill the packet (`3 + 27 = 30`). 110 addresses take 13 packets. The host sends indexes 0–109. Firmware paints 0–99 and acknowledges 100–109 without writing them.

Clear `0xA8`:

| Bytes | Content |
| --- | --- |
| 0 | `0xA8` |
| 1–4 | ASCII `A96K` |

The keymap echoes `0xA8` and returns to the normal matrix effect. A wrong magic byte is answered with `0xFF` and the overlay stays.

## Timeout and disconnect

Each accepted `0xA7` starts a 2000 ms timer. A probe with version `1`, while the overlay is already up, refreshes that timer. Silence, USB suspend, unplug, or a non-USB link clears the overlay. The Super-held highlight in the keymap then works on its own: basic keys on the Mac or Windows base layer, and it stays out of the way while Fn or the M layer is showing the readable lights.

Flashing steps, the pinned QMK commit, and how to return to official 2.1.5 are in [firmware/README.md](../firmware/README.md).
