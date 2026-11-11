# What was checked

No Air96, no Omarchy install, and no Quickshell were available in the environment that produced this plugin. QML was not executed. Nothing was flashed onto a keyboard. The Omarchy keymap was compiled in this environment; the `.bin` is produced by `firmware/build.sh` and by the `firmware` GitHub Actions workflow (artifact `nuphy-air96-v2-omarchy`). It is not committed.

## Unit tests

`python3 -m unittest discover -s tests -v` covers logic that does not need hardware:

| Area | What the tests do |
| --- | --- |
| Theme | `colors.toml` accent, comments, quotes, and `keyboard.rgb` with or without `#`. A bare `ff00ff` wins over the accent. |
| Home Assistant | Theme follow sends the theme color and omits brightness unless `sync_brightness` is on. A manual color always sends that color and the lamp brightness. `only_when_on` reads `GET /api/states/<entity>` and skips lights that are not on. Token resolution strips paste markers. Missing, malformed, and unreadable tokens are different errors, and the token text is not in the message or the body. |
| Protocol | 100 keys, LED indexes, VIA lighting packets, HSV, keymap offsets, the per-key probe, the 9-LED packet split, clear, and the timeout model. A model of QMK's `raw_hid_receive` answers the version query unless the keymap claims the packet without sending. |
| Screensaver | A fake `/proc` cmdline matches `org.omarchy.screensaver` and `omarchy-launch-screensaver`, and ignores a command line that contains `air96_`. Breathing is effect 5 at speed 153, is not EEPROM-saved, and solid color returns when the process is gone. A stored effect of 4 is migrated to 5. |
| Backend | Theme follow sends solid color and skips a duplicate save. Follow off does not write on sync. A custom-firmware probe is answered with clear (`0xA8`) and then the VIA solid color, with no per-key paint. Old `music`, `per_key`, `modifiers`, and `profiles` sections load and are dropped. Snapshot omits the token. Keymap apply conflicts leave the keyboard unchanged. |
| HID discovery | The report-descriptor parser finds usage page `0xFF60` usage `0x61`. Only product ids `0x3265` and `0x3266` match, not an Air75 id. |
| CLI and worker | `main(["--help"])` and every subcommand run with the device layer mocked. The worker reads one NDJSON request from a pipe and exits. inotify, a fake Hyprland socket, evdev `open_nodes`, and a local Home Assistant HTTP POST are exercised the same way. |
| Install | `install.sh` writes the theme hook and CLI path under a temporary `HOME`. The hook runs `sync` from that path and from a plugin checkout, and exits 0 when the CLI is missing. |

## Implemented, not run on hardware

- Opening `/dev/hidraw`, the 32-byte VIA transaction, and the `EINVAL` report-id retry.
- Lighting get, set, and EEPROM save.
- Full keymap read and single-key write.
- inotify against Omarchy's live theme directory, and a theme change on a running Omarchy. The hook path was checked against basecamp/omarchy `quattro`: `omarchy-hook theme-set` runs `~/.config/omarchy/hooks/theme-set.d/*` after `~/.local/state/omarchy/current/theme` has been replaced. `./install.sh` was exercised in a temporary home, not on that machine.
- Hyprland socket2 `activewindow` and `submap` events.
- Home Assistant HTTP POST.
- Evdev open on a real event node. The 24-byte `input_event` layout is the 64-bit one Omarchy uses. A 32-bit kernel is not parsed.
- The bar panel. The widget host follows the clock bar widget (`BarWidget`, its own `ShellIpc` target, panel loaded by URL). This repo was not opened in Quickshell.

## Not available on stock firmware

The plugin paints the whole board with the VIA solid color. On the Omarchy keymap it sends clear (`0xA8`) first so a leftover per-key overlay cannot hide that color. It does not send per-key frames. No reflash is required for theme follow, the lamp, or the screensaver Breathing effect. See [PER-KEY.md](PER-KEY.md).
