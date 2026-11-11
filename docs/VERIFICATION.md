# What was checked

No Air96, no Omarchy install, and no Quickshell were available in the environment that produced this plugin. QML was not executed. Nothing was flashed onto a keyboard. The Omarchy keymap was compiled in this environment; the `.bin` is produced by `firmware/build.sh` and by the `firmware` GitHub Actions workflow (artifact `nuphy-air96-v2-omarchy`). It is not committed.

## Unit tests

`python3 -m unittest discover -s tests -v` covers logic that does not need hardware:

| Area | What the tests do |
| --- | --- |
| Theme | `colors.toml` accent, comments, quotes, and `keyboard.rgb` with or without `#`. A bare `ff00ff` wins over the accent. |
| Binds | `hyprctl binds -j` and `bind` / `bindd` lines, XKB `code:` keys, submaps, idle Super keys versus a held mask. Evdev bytes update only Shift, Ctrl, Alt, and Super. |
| Profiles | Shipped Firefox, Code, and Minecraft matches. A user file with the same id overrides. VS Code import keeps the first chord. |
| Home Assistant | `light.turn_on` body, entity and URL checks, token resolution. The token is not in the body. |
| Protocol | 100 keys, LED indexes, VIA lighting packets, HSV, keymap offsets, the per-key probe, the 9-LED packet split, clear, and the timeout model. |
| Music | Synthetic PCM through the FFT, column and VU color mapping, and a stock VIA pulse that does not bump the EEPROM save counter. |
| Backend | Theme follow sends solid color and skips a duplicate save. Follow off does not write. Snapshot omits the token. Stock probe refuses per-key. A fake custom ack stores a frame. Keymap apply conflicts leave the keyboard unchanged. |
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
- The bar panel. It follows the Omarchy Quickshell widgets used by the reference plugin, but this repo was not opened in Quickshell.

## Not available on stock firmware

Per-key RGB. The panel still draws the highlights, and music mode falls back to a global VIA pulse. See [PER-KEY.md](PER-KEY.md) and [firmware/README.md](../firmware/README.md). The keymap compiled here was not flashed, and the music recorder was not pointed at a live PipeWire monitor.
