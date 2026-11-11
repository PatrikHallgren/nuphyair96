# NuPhy Air96 for Omarchy

Omarchy bar plugin for the NuPhy Air96 V2 (the 2.1.x firmware generation). It sets the RGB backlight, can follow the active Omarchy theme, remaps keys on a picture of the 96% layout, and can push that color to Home Assistant lights. A second view highlights Hyprland and per-app keys. Stock firmware cannot paint individual keys. The [Omarchy keymap](firmware/README.md) adds that, and a music mode can drive it from the system audio monitor.

The Air96 is a QMK/VIA keyboard. It is not the protocol used by [fldc/omarchy-nuphy](https://github.com/fldc/omarchy-nuphy) for the Air75 V3. This plugin keeps that project's shape: a Quickshell service, one Python worker, theme watching, and an explicit Apply for keymap changes. The worker, watcher, and panel structure are adapted from that project. Copyright 2026 Fredrik Storm, MIT. See [LICENSE](LICENSE).

Nothing here was run on an Air96. [docs/VERIFICATION.md](docs/VERIFICATION.md) splits tested logic from code that still needs your keyboard.

## What the keyboard actually speaks

| | |
| --- | --- |
| USB | vendor `19F5`, product `3266` in NuPhy's JSON, product `3265` on reported 2.1.x firmware |
| Interface | VIA raw HID, usage page `FF60` usage `61`, 32-byte reports |
| Matrix | 6×21, 8 EEPROM layers, 100 keys |
| LEDs | 110. Keys are 0–99. Side strips are 100–109 and are not VIA-addressable |
| Cable | USB only. Bluetooth and the 2.4G dongle do not expose VIA |

Details and packet layouts are in [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Install

Omarchy:

```sh
omarchy plugin add https://github.com/PatrikHallgren/nuphyair96 --enable
```

The plugin id is `local.nuphy-air96`, so it can sit next to the Air75 plugin. The bar icon IPC target is `air96`:

```sh
omarchy-shell air96 toggle
```

Python 3 from the standard library is enough. No pip packages.

For a local checkout:

```sh
ln -s "$(pwd)" ~/.config/omarchy/plugins/local.nuphy-air96
```

Then enable `local.nuphy-air96` the same way as any other local Omarchy plugin and restart the shell.

## Permissions

Copy the HID rule, reload udev, and replug the USB cable:

```sh
sudo cp udev/70-nuphy-air96.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw
```

The rule only adds `TAG+="uaccess"` for these two product ids. Seatd turns that into an ACL for the active seat. It does not set a mode or a group, and it does not match every NuPhy board.

Check discovery without writing anything:

```sh
python3 air96_cli.py devices
python3 air96_cli.py status
```

`setupIssue: "hid-permission"` means the node exists but this user cannot read and write it. `not-found` means no matching raw HID interface (cable unplugged, or only the dongle is connected).

## Config

`~/.config/omarchy-nuphy-air96/config.json` is created on first save, mode `0600`. [config.example.json](config.example.json) matches the defaults.

Theme follow is off until you turn it on, so installing the plugin does not change the keyboard. Brightness, speed, and effect are integers 0–255. Effect `1` is solid color.

State, including keymap backups, lives in `~/.local/state/omarchy-nuphy-air96/`.

## Backlight and theme

The Lighting tab sends VIA channel 3: effect, brightness, speed, and hue/saturation. Apply writes them and then saves to EEPROM.

Follow reads the active theme at `$XDG_STATE_HOME/omarchy/current/theme` (usually `~/.local/state/omarchy/current/theme`):

1. `keyboard.rgb`, first line that is a color. `#RRGGBB`, bare `RRGGBB`, and a `0x` prefix are all accepted. Tokyo Night ships bare `ff00ff`, so a hash-only reader would miss it.
2. Otherwise `accent` in `colors.toml`.

While follow is on, the default is to switch to solid color so the theme hue is visible. Turn off "Use solid color while following" to keep the current effect and only update hue and saturation. Brightness and speed stay as they are. The same color is not written twice.

The worker watches the theme directory with inotify. A theme-set hook is also included, because a copied hook cannot use a relative path:

```sh
mkdir -p ~/.config/omarchy/hooks/theme-set.d
cp hooks/theme-set.d/50-air96-sync ~/.config/omarchy/hooks/theme-set.d/
chmod +x ~/.config/omarchy/hooks/theme-set.d/50-air96-sync
```

The hook runs `air96_cli.py sync`, which does nothing when follow is off. You can also run `python3 air96_cli.py sync --force`.

Side strips stay on the keyboard's own `SIDE_*` keys.

## Keymap

The Keys tab reads the dynamic keymap and draws the 100-key layout. Pick a layer (Windows is layer 2, which is what Linux normally uses), pick a key, search a keycode, then Apply.

Apply writes only the staged keys. It re-reads first, and if a cell changed since the read it writes nothing and reports the conflict. A JSON backup is stored under the state directory before a successful write. Factory defaults are not exposed over VIA, and this plugin never sends the VIA EEPROM-reset or bootloader commands.

## Home Assistant

Optional. When enabled, a successful keyboard color write also POSTs `light/turn_on` with `rgb_color` and `brightness`. You can push once from the panel without changing the keyboard.

The token is the `HA_TOKEN` environment variable, a `token_file`, or `token` in the config. Prefer the environment or a file. The panel never shows the token, and status JSON does not contain it. Only `http` and `https` URLs are accepted. Entity ids must look like `light.desk`.

```sh
export HA_TOKEN=...   # long-lived token, not a shell history line you commit
python3 air96_cli.py apply --hex '#7aa2f7' --effect 1
```

## Keybind highlights

The Binds tab reads `hyprctl binds -j` and, when the shell is running, Hyprland's `socket2` for the focused window, submap, and config reloads.

With no modifier held, keys that complete a Super bind in the current submap are dim. Mouse binds and catch-alls are skipped. When a modifier mask is known, only keys that complete that exact mask are bright. Super+Shift is mask 65. The highlight is the non-modifier key, so a Windows-mode Option keycap that sends Super is not itself the lit key.

Hyprland's socket does not report modifier state. Detection is an optional evdev listener, off by default. It reads the 64-bit `input_event` (24 bytes), keeps Shift, Ctrl, Alt, and Super, and drops every other key without logging it. It does not grab the device. Turning the switch on does not open the event node until the shell restarts.

Install the second udev rule only if you want that:

```sh
sudo cp udev/70-nuphy-air96-modifiers.rules /etc/udev/rules.d/
sudo udevadm control --reload
```

Replug, enable listening, restart the shell. The `input` group also works and exposes every keyboard, so the seat ACL on this device is the narrower choice. The kernel still delivers every key on that node; only this process ignores them.

## App profiles

When the focused window class changes, a profile can highlight extra keys. An active Hyprland bind on the same key wins.

Profiles are JSON:

```json
{
  "id": "firefox",
  "name": "Firefox",
  "match": {"class": ["firefox"], "title_contains": []},
  "keys": [{"key": "t", "mods": ["ctrl"], "label": "New tab", "color": "#89b4fa"}]
}
```

Class match is exact, ignoring case. `title_contains` is an extra substring check. Shipped examples are Firefox, Code/Cursor, and Minecraft, in `profiles/`. A file with the same `id` in `~/.config/omarchy-nuphy-air96/profiles/` replaces the shipped one. `"enabled": false` disables that id.

VS Code can be imported from `keybindings.json`. The first chord is kept. Commands that start with `-` are skipped.

```sh
python3 air96_cli.py import-vscode ~/.config/Code/User/keybindings.json > ~/.config/omarchy-nuphy-air96/profiles/vscode.json
```

Games do not share an export format. Steam, Lutris, and Minecraft `options.txt` would each need their own parser. The Minecraft example is hand-written, not imported.

## Per-key RGB

Not possible on stock firmware. The Binds tab still draws the highlights on screen. `push_to_keyboard` defaults to on: after a successful `0xA6` probe the worker sends `0xA7` frames and resends them about once a second. Stock firmware answers the probe with `0xFF` and the matrix effect is left alone. The command set, the 2 second timeout, and the USB-unplug clear are in [docs/PER-KEY.md](docs/PER-KEY.md). Flash steps are in [firmware/README.md](firmware/README.md).

## Music

The Binds tab has a Music lighting switch. The same switch from a shell:

```sh
python3 air96_cli.py music on
python3 air96_cli.py music off
python3 air96_cli.py music on --effect vu
```

`spectrum` paints columns across the keyboard. `vu` uses one level for every key. Colors are tinted by the theme accent, or by the configured hex color when theme follow is off. The bar plugin has to be running; the command only saves the setting.

Audio is the PipeWire or PulseAudio monitor (`pw-record`, or `parecord` if that is what the system has). No extra Python packages. On the Omarchy keymap the frames use the per-key protocol. On stock firmware the worker pulses global brightness and hue through VIA about four times a second and does not write those pulses to EEPROM. Stopping music restores the saved effect.

The visualizer idea and the 9-LED batch layout come from [ravila4/nuphy-rgb-music](https://github.com/ravila4/nuphy-rgb-music) by Ricardo Avila, MIT. The capture and FFT here are separate, and the command bytes stay the Air96 probe.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The suite parses every CLI subcommand, runs `main(["--help"])`, and drives the worker, theme watcher, Home Assistant client, and evdev listener with mocks. It does not open a keyboard.

## What to try on the keyboard

Use the USB cable.

1. `python3 air96_cli.py devices` shows one Air96 and `python3 air96_cli.py status` says `connected` after the udev rule. Try both product ids if you have more than one board, or if a firmware update changes the id.
2. Apply solid white, then a non-solid effect, and confirm the index matches the name in the dropdown. If 2.1.x shifted the list, the number on the keyboard is the one to trust.
3. Turn on theme follow and switch themes, including Tokyo Night (`keyboard.rgb` is `ff00ff` with no hash). The keyboard should change once, not on a timer.
4. Read the keymap, change one Windows-layer key, Apply, and confirm it. Change that key in VIA or on another host, then Apply the old draft: the plugin should refuse and leave the new value in place.
5. Point Home Assistant at one `light.*` entity and confirm the room light follows a successful color write. Confirm `status` does not print the token.
6. Open the Binds tab. Super keys should be dim before you enable evdev. After the modifier rule, a replug, and a shell restart, hold Super and then Super+Shift and check that the bright keys change.
7. Focus Firefox, then a terminal. Firefox keys should appear only on Firefox. On stock firmware the per-key probe should fail and the physical backlight should stay on the VIA effect.
8. After flashing the Omarchy keymap, `status` should show `perKey.supported` true. Turn on push if it is off. Super binds should appear on the keys, and killing the bar plugin should return the normal effect within about two seconds. Fn readable lights should still show while Fn is held.
9. Turn music on with something playing. The keys should move. Turn it off and the previous effect should come back. On a stock board, the same switch should only pulse the global color.

The QML panel was not launched here. If the bar icon fails to load, the Python CLI still applies lighting and syncs the theme.

## Layout of the repo

| Path | Role |
| --- | --- |
| `manifest.json`, `Service.qml`, `Widget.qml`, `Editor.qml` | Omarchy service and bar panel |
| `air96_worker.py` | Long-running NDJSON process |
| `air96_cli.py` | `status`, `devices`, `sync`, `apply`, `import-vscode` |
| `air96_protocol.py`, `air96_hid.py`, `air96_layout.py` | VIA packets, hidraw discovery, 100-key map |
| `profiles/` | Example window profiles |
| `udev/` | Seat ACL rules, not installed automatically |
| `hooks/theme-set.d/50-air96-sync` | Optional theme hook |
