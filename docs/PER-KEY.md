# Per-key lighting

Stock Air96 V2 firmware cannot show a host-chosen color on one key.

- VIA RGB channel 3 sets one effect, one hue, one saturation, one brightness, and one speed for the whole matrix.
- `side.c` owns LEDs 100–109 and only changes them for `SIDE_*` keycodes.
- The effect task overwrites key colors every frame.

What works today is the on-screen keyboard in the bar panel. `per_key.push_to_keyboard` stays off. When it is on, the worker probes once. A stock board answers `0xFF` and the plugin leaves the matrix effect alone. A board that acknowledges the probe below receives frames. Turning the push back off reapplies the VIA effect.

Do not EEPROM-save these frames. They are a live overlay.

## Probe and write

Both packets are 32 bytes.

Probe `0xA6`:

| Bytes | Content |
| --- | --- |
| 0 | `0xA6` |
| 1–4 | ASCII `A96K` |
| 5 | version `1` |

Stock firmware: byte 0 comes back `0xFF`. Custom firmware that implements this: byte 0 is `0xA6`, bytes 1–4 are `A96K`, byte 5 is `1`.

Set `0xA7`:

| Bytes | Content |
| --- | --- |
| 0 | `0xA7` |
| 1 | first LED index |
| 2 | count, 1–9 |
| 3–29 | RGB triples |

Nine LEDs fill the packet (`3 + 27 = 30`). 110 LEDs take 13 packets. The host sends indexes 0–109. Firmware should paint 0–99 and leave 100–109 to `side.c`.

## Firmware sketch

This is an untested sketch of the missing piece. It is not a firmware image, it is not a fork of QMK, and it has not been compiled. Flash only a tree you build and read yourself.

```c
/* air96_per_key.h — proposed, not part of stock NuPhy firmware */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define AIR96_PER_KEY_MAGIC "A96K"
#define AIR96_PER_KEY_VERSION 1

void air96_per_key_probe(uint8_t *data, uint8_t length);
void air96_per_key_set(uint8_t *data, uint8_t length);
bool air96_per_key_active(void);
void air96_per_key_paint(void); /* call from rgb_matrix_indicators_user for LEDs 0-99 */
```

In `via_command_kb`, handle `0xA6` and `0xA7` before the default unhandled path. Keep a 110-by-3 framebuffer and a boolean. `0xA6` writes the ack described above and does not change EEPROM. `0xA7` copies the triples and sets the boolean. `rgb_matrix_indicators_user` calls `rgb_matrix_set_color` for LEDs 0–99 while the boolean is set. Do not write LEDs 100–109. Add a way to clear the boolean when the host sends VIA channel 3 again, or when the probe version is 0, so the normal effect returns.

Until that runs on hardware, treat every per-key color on the physical keyboard as unavailable.
