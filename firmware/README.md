# Air96 V2 Omarchy firmware

Per-key host colors for the NuPhy Air96 V2. The keymap is built on top of [ablasik/nuphy-qmk](https://github.com/ablasik/nuphy-qmk) at commit `6101403bd61ffed5b9c1642d45bb742c263a815b` (v1.2.4). That tree already has the Fn readable lights, the IS31FL3733 matrix, and a dfu-util flash path. This repo only adds the `omarchy` keymap. It does not replace the bootloader, and it does not replace the closed-source 2.4G dongle firmware.

The keymap is GPL-2.0-or-later because it is built with QMK and includes NuPhy's keymap and the game-mode effect. The Python plugin in the repository root stays MIT. See the SPDX headers in this directory.

## What the host can do

Raw HID, 32-byte reports, no report id, same usage page as VIA (`FF60` / `61`). VIA commands are unchanged. This keymap's `via_command_kb` returns false for them so QMK calls `raw_hid_send`. It returns true only for `0xA6` / `0xA7` / `0xA8`, and only after it has sent the reply. A `void` hook still links over QMK's weak `bool` function and then drops every reply, which is why `status` timed out on the first flashed build.

| Command | Bytes | Result |
| --- | --- | --- |
| Probe `0xA6` | `A96K`, version `1` | Echoes the magic and version, then 100 paintable LEDs, 9 LEDs per packet, flags, and timeout `2000` ms |
| Set `0xA7` | index, count 1–9, RGB triples | One packet paints one key when count is 1, or a batch of up to 9. Indexes 100–109 are acknowledged and left to the side strips |
| Clear `0xA8` | `A96K` | Drops the overlay and returns to the normal matrix effect. Nothing is written to EEPROM |

A probe with version byte `0` also clears. A probe while the overlay is already up refreshes the 2 second timer. If the host stops sending for 2 seconds, or the link leaves USB (unplug, suspend, Bluetooth, or the dongle), the overlay drops. The plugin resends the current highlight about once a second so a still image stays up.

Holding Super (the GUI modifier), while the host overlay is off, lights the basic keys on the Mac or Windows base layer. Fn and the M layer keep the readable-light colors from ablasik's firmware. That fallback needs no host.

USB only. Bluetooth and the 2.4G dongle do not expose this raw HID interface. The Super fallback still runs on the keyboard itself.

The build rewrites the USB product id from ablasik's `0x3265` to `0x3266`, which is the id on current official 2.1.5 boards. The bootloader stays `0483:DF11`.

## Build

The image is not committed. GitHub Actions workflow `firmware` builds it and uploads the artifact `nuphy-air96-v2-omarchy` (`nuphy_air96_v2_ansi_omarchy.bin`).

Locally, with `gcc-arm-none-eabi`, `dfu-util` (QMK uses `dfu-suffix` while packing the image), and the QMK CLI (`python3 -m pip install --user qmk`, and `~/.local/bin` on `PATH`):

```sh
firmware/build.sh
```

The script clones the pinned tree and its submodules under `firmware/.build/` and copies the bin to `firmware/.build/nuphy_air96_v2_ansi_omarchy.bin`.

## Flash on Linux

Use the USB cable. `dfu-util` is the only tool. The plugin does not flash anything.

1. Unplug the keyboard.
2. Hold Esc and plug the USB cable in. Release Esc when the board enumerates as `0483:DF11`.
3. Flash and leave the bootloader:

```sh
dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D nuphy_air96_v2_ansi_omarchy.bin
```

If Esc+plug does not enter the bootloader, the recovery button is under the Caps Lock keycap. Hold that button and plug the cable in, then run the same command.

The first boot after leaving stock firmware resets the VIA keymap and lighting once. Later flashes of this keymap keep VIA settings when the link config is still valid. Expect to redo key assignments after the first switch.

If `status` says the keyboard did not answer after a flash of the first Omarchy image, flash this image again. That image enumerated the raw HID interface and accepted the report, then never sent one back. Typing was unaffected. `--debug` on the CLI prints the bytes that got no reply.

## Back to official 2.1.5

Download NuPhy's Air96 V2 2.1.5 QMK image from NuPhy support (the firmware package they publish for that version). Put the keyboard in the bootloader the same way and flash that file with the same `dfu-util` command, swapping the filename. The bootloader itself is not overwritten by either image. The RF module and the dongle are a separate NuPhy update and are not in this bin.

## Credits

- [ablasik/nuphy-qmk](https://github.com/ablasik/nuphy-qmk), GPL-2.0-or-later, which carries NuPhy and adi4086's Air96 work.
- QMK Firmware, GPL-2.0-or-later.
- The batch size of 9 RGB triples matches the streaming layout in [ravila4/nuphy-rgb-music](https://github.com/ravila4/nuphy-rgb-music) (Ricardo Avila, MIT). The command bytes here stay `0xA6` / `0xA7` / `0xA8` so the plugin probe does not change. That project targets the Air75 V2, not this board.
