# What was checked

No Air96, no Omarchy install, and no Quickshell were available in the environment that produced this plugin. QML was not executed. Nothing was flashed.

## Unit tests

`python3 -m unittest discover -s tests -v` covers logic that does not need hardware:

| Area | What the tests do |
| --- | --- |
| Theme | `colors.toml` accent, comments, quotes, and `keyboard.rgb` with or without `#`. A bare `ff00ff` wins over the accent. |
| Binds | `hyprctl binds -j` and `bind` / `bindd` lines, XKB `code:` keys, submaps, idle Super keys versus a held mask. Evdev bytes update only Shift, Ctrl, Alt, and Super. |
| Profiles | Shipped Firefox, Code, and Minecraft matches. A user file with the same id overrides. VS Code import keeps the first chord. |
| Home Assistant | `light.turn_on` body, entity and URL checks, token resolution. The token is not in the body. |
| Protocol | 100 keys, LED indexes, VIA lighting packets, HSV, keymap offsets, the per-key probe, and the 9-LED packet split. |
| Backend | Theme follow sends solid color and skips a duplicate save. Follow off does not write. Snapshot omits the token. Stock probe refuses per-key. A fake custom ack stores a frame. Keymap apply conflicts leave the keyboard unchanged. |
| HID discovery | The report-descriptor parser finds usage page `0xFF60` usage `0x61`. Only product ids `0x3265` and `0x3266` match, not an Air75 id. |
| CLI and worker | `main(["--help"])` and every subcommand run with the device layer mocked. The worker reads one NDJSON request from a pipe and exits. inotify, a fake Hyprland socket, evdev `open_nodes`, and a local Home Assistant HTTP POST are exercised the same way. |

## Implemented, not run on hardware

- Opening `/dev/hidraw`, the 32-byte VIA transaction, and the `EINVAL` report-id retry.
- Lighting get, set, and EEPROM save.
- Full keymap read and single-key write.
- inotify against Omarchy's live theme directory and the installed theme-set hook. A temporary directory is covered by the unit tests.
- Hyprland socket2 `activewindow` and `submap` events.
- Home Assistant HTTP POST.
- Evdev open on a real event node. The 24-byte `input_event` layout is the 64-bit one Omarchy uses. A 32-bit kernel is not parsed.
- The bar panel. It follows the Omarchy Quickshell widgets used by the reference plugin, but this repo was not opened in Quickshell.

## Not available on stock firmware

Per-key RGB. The panel still draws the highlights. See [PER-KEY.md](PER-KEY.md).
