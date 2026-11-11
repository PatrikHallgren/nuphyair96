# NuPhy Air96 for Omarchy

Omarchy bar plugin for the NuPhy Air96 V2 (the 2.1.x firmware generation). The whole keyboard is one solid color. It can follow the active Omarchy theme, or a color and brightness you pick. The same choices exist for a Home Assistant lamp. While the Omarchy screensaver is running the keyboard can play the Breathing effect in that color, then return to solid. The Keys tab is a picture of the Air96, the same idea as the Air75 map in [fldc/omarchy-nuphy](https://github.com/fldc/omarchy-nuphy).

Music reaction and Super key highlighting are gone. Old `music`, `per_key`, `modifiers`, and `profiles` sections in `config.json` are ignored. The color is a VIA matrix command. On the already-flashed Omarchy keymap the plugin sends clear first so a leftover per-key overlay cannot hide it. No reflash is required.

The Air96 is a QMK/VIA keyboard. It is not the protocol used by [fldc/omarchy-nuphy](https://github.com/fldc/omarchy-nuphy) for the Air75 V3. This plugin keeps that project's shape: a Quickshell service, one Python worker, theme watching, and an explicit Apply for keymap changes. The worker, watcher, and panel structure are adapted from that project. Copyright 2026 Fredrik Storm, MIT. See [LICENSE](LICENSE).

Nothing here was run on an Air96. [docs/VERIFICATION.md](docs/VERIFICATION.md) splits tested logic from code that still needs your keyboard.

## Quick start

`apply --follow on` writes the current theme once. Later theme changes reach the keyboard only if something runs `sync`. The bar worker does that when the plugin is enabled. Without the bar, Omarchy's theme-set hook does it. Neither is installed by cloning the repo.

Current Omarchy (`quattro`) finishes a theme change by running `omarchy-hook theme-set <name>`. That executes every file in `~/.config/omarchy/hooks/theme-set.d/` with bash, after `~/.local/state/omarchy/current/theme` is already the new theme. stdout from the hook is discarded. A failing hook is logged and does not undo the theme.

CLI only, which is enough for theme follow:

```sh
git clone https://github.com/PatrikHallgren/nuphyair96.git
cd nuphyair96
./install.sh --no-plugin
python3 air96_cli.py apply --follow on
```

The next theme change runs `air96_cli.py sync` from this checkout. `sync` does nothing until follow is on. The hook does not need the bar plugin.

Bar plugin as well. `./install.sh` with no arguments links this checkout to `~/.config/omarchy/plugins/local.nuphy-air96`, restarts the bar worker, and asks Omarchy to put the icon on the right side of the bar. A link alone does not draw the icon. The icon appears when `local.nuphy-air96` is in `~/.config/omarchy/shell.json`.

```sh
./install.sh
omarchy plugin enable local.nuphy-air96 --section right
omarchy-restart-shell
```

`omarchy plugin enable` takes a placement (`--section right`), not `--yes`. `./install.sh` runs `omarchy-shell shell rescanPlugins`, then that enable command, then `omarchy-restart-shell`. The restart is what loads the widget. `listPlugins` can say the plugin is enabled before the icon exists.

```sh
python3 air96_cli.py doctor
python3 air96_cli.py panel
```

Click `K A96`, or run `panel`. Both open the popup. `panel` calls `omarchy-shell air96 toggle`. On more than one monitor that command opens the popup on the focused screen; a click opens the copy on the bar that was clicked. `doctor` prints the plugin path, the files, whether `shell.json` lists the widget, and the slot from `omarchy-shell shell debugBarGeometry` (width, height, visible). If the popup file fails to load, the click still opens a card with the QML error. Shell warnings are in the journal:

```sh
journalctl --user -t omarchy-shell -n 200 --no-pager
```

From Omarchy, without a separate checkout:

```sh
omarchy plugin add https://github.com/PatrikHallgren/nuphyair96 --enable --yes
~/.config/omarchy/plugins/local.nuphy-air96/install.sh --no-plugin
python3 ~/.config/omarchy/plugins/local.nuphy-air96/air96_cli.py apply --follow on
```

Remove the hook, the recorded CLI path, and a plugin symlink this script created. A leftover `.previous` copy, and `config.json`, stay:

```sh
./install.sh --uninstall
omarchy plugin disable local.nuphy-air96
omarchy plugin remove local.nuphy-air96 --yes
```

The HID udev rule is still a separate sudo copy. See Permissions.

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

Use [Quick start](#quick-start). `./install.sh` is the install path. Python 3 from the standard library is enough. No pip packages.

The plugin id is `local.nuphy-air96`, so it can sit next to the Air75 plugin.

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
python3 air96_cli.py --debug status
```

`setupIssue: "hid-permission"` means the node exists but this user cannot read and write it. `not-found` means no matching raw HID interface (cable unplugged, or only the dongle is connected). `--debug` prints the 32-byte report that was written and whether a report came back or the read timed out.

## Config

`~/.config/omarchy-nuphy-air96/config.json` is created on first save, mode `0600`. [config.example.json](config.example.json) matches the defaults.

A new config follows the theme. A file you already saved keeps its `follow_theme` value until you change it in the panel or with `apply --follow on`. Brightness is an integer 0–255. The keyboard effect is always solid (`1`) except while the screensaver light show is on, which uses Breathing (`5`) and does not write that effect to EEPROM. An old saved `screensaver.effect` of `4` is read as `5`.

State, including keymap backups, lives in `~/.local/state/omarchy-nuphy-air96/`.

## Backlight and theme

The Lighting tab sets follow, a color, and brightness for the keyboard, and the same three for the lamp. Toggles apply immediately. Color and brightness use Apply keyboard or Save lights. The keyboard write is VIA channel 3: solid effect, brightness, speed, and hue/saturation, then an EEPROM save. If the per-key probe succeeds, clear (`0xA8`) is sent first.

Follow reads the active theme at `$XDG_STATE_HOME/omarchy/current/theme` (usually `~/.local/state/omarchy/current/theme`):

1. `keyboard.rgb`, first line that is a color. `#RRGGBB`, bare `RRGGBB`, and a `0x` prefix are all accepted. Tokyo Night ships bare `ff00ff`, so a hash-only reader would miss it.
2. Otherwise `accent` in `colors.toml`.

While follow is on, the board is solid in the theme color. Brightness still applies. With follow off, the chosen hex is used. The same color is not written twice.

The bar worker watches the theme directory with inotify. The theme-set hook installed by `./install.sh` is the path that works when the bar is not running. It calls `air96_cli.py sync`, which does nothing when follow is off. You can also run `python3 air96_cli.py sync --force`. When a theme change is started from the menu, Omarchy writes hook errors to `~/.local/state/omarchy/theme-set.log`.

Side strips stay on the keyboard's own `SIDE_*` keys.

## Keymap

The Keys tab reads the dynamic keymap and draws the 100-key layout. Pick a layer (Windows is layer 2, which is what Linux normally uses), pick a key, search a keycode, then Apply.

Apply writes only the staged keys. It re-reads first, and if a cell changed since the read it writes nothing and reports the conflict. A JSON backup is stored under the state directory before a successful write. Factory defaults are not exposed over VIA, and this plugin never sends the VIA EEPROM-reset or bootloader commands.

## Home Assistant

Optional, and independent of the keyboard switch. The default entity is `light.floor_lamp_66fa` at `http://homeassistant.local:8123`. A saved config keeps the entities already in the file.

While the lamp follows the theme, `light/turn_on` sends `rgb_color` only, so the lamp keeps its own brightness. Turn on "Also set lamp brightness while following the theme" (`sync_brightness`) to send `home_assistant.brightness` as well. With follow off, the chosen lamp color and lamp brightness are always sent. Lamp brightness is separate from the keyboard brightness. 180 is about 71%.

`light.turn_on` turns a light on. `home_assistant.only_when_on` defaults to true: the plugin GETs `/api/states/<entity>` and does not call a light whose state is not `on`. A theme change then leaves an off lamp off. Turn the option off, or turn off "Only when the light is already on", if the lamp should come on with the theme. If every configured light is off, nothing is posted. `ha-test` follows the same rules and says so instead of printing an HTTP status.

The token is an inline config value, then the `HA_TOKEN` environment variable, then `token_file`. Prefer the file. The panel never shows the token, and status JSON does not contain it. Only `http` and `https` URLs are accepted. Entity ids must look like `light.desk`.

Save the token with the CLI. The prompt does not echo. Paste markers from the terminal (`ESC[200~` / `ESC[201~`) and surrounding whitespace are removed before the file is written, mode `0600`.

```sh
python3 air96_cli.py ha-token
python3 air96_cli.py ha-test
```

`ha-test` pushes the current color once and prints the HTTP status. It does not print the token. Set the URL and at least one `light.*` entity in the config or the panel first.

Do not fill the file with `read -rsp`. That keeps bracketed-paste bytes in the token. A file of those bytes used to be reported as a missing token.

The three failures are separate, and none of them includes the token text:

- missing: no inline token, no environment value, and an empty file
- malformed: after the paste markers are removed, the token is too short or still has whitespace or control characters
- unreadable: the token file cannot be opened

`HA_TOKEN` in the environment overrides the file. `ha-token` says so when that variable is set, without printing its value.

## Screensaver

The Lighting tab switch, or:

```sh
python3 air96_cli.py screensaver on
python3 air96_cli.py screensaver off
```

The bar worker looks about once a second for a process whose command line contains `org.omarchy.screensaver`, `omarchy-screensaver`, or `omarchy-launch-screensaver`. It ignores its own `air96_` process. While that process is up and the switch is on, the keyboard uses Breathing. On the flashed Omarchy keymap that is effect 5, because Alphas Mods occupies index 2 and index 4 is only a left/right gradient. The live speed is 153, which is the firmware default, so a stored speed of 0 cannot freeze the pulse. Neither the effect nor that speed is written to EEPROM. When the screensaver exits, solid color and the saved speed return, also without a new EEPROM write. The worker does not paint solid color over the show. A crash or reboot therefore returns to the last saved solid color.

To see the pulse without waiting for the screensaver:

```sh
python3 air96_cli.py screensaver test
```

That runs Breathing for 10 seconds and restores solid color. The bar worker is locked out for those 10 seconds so it cannot paint over the test.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The suite parses every CLI subcommand, runs `main(["--help"])`, and drives the worker, theme watcher, Home Assistant client, and evdev listener with mocks. It does not open a keyboard.

## What to try on the keyboard

Use the USB cable.

1. `python3 air96_cli.py devices` shows one Air96 and `python3 air96_cli.py status` says `connected` after the udev rule. Try both product ids if you have more than one board, or if a firmware update changes the id.
2. Apply solid white, then a non-solid effect, and confirm the index matches the name in the dropdown. If 2.1.x shifted the list, the number on the keyboard is the one to trust.
3. `./install.sh --no-plugin`, then `apply --follow on`, then switch themes, including Tokyo Night (`keyboard.rgb` is `ff00ff` with no hash). The keyboard should change without running the command again. Without that hook, follow only applies when you run it yourself.
4. Read the keymap, change one Windows-layer key, Apply, and confirm it. Change that key in VIA or on another host, then Apply the old draft: the plugin should refuse and leave the new value in place.
5. Point Home Assistant at one `light.*` entity and confirm an already-on light follows a successful color write without changing brightness. An off light stays off. Confirm `status` does not print the token.
6. `./install.sh`, then `python3 air96_cli.py apply --follow on`. The whole board should match the theme, including after a theme switch and after the worker restarts. Brightness in the panel should change the board whether or not follow is on. With follow off, the chosen color should stick.
7. Turn the lamp follow on in the panel and confirm `light.floor_lamp_66fa` takes the theme color without a brightness jump. Turn follow off, pick a color and a brightness, and confirm both. An off lamp stays off while "Only when the light is already on" is enabled.
8. `python3 air96_cli.py screensaver test`. The whole board should pulse for about 10 seconds, then return to solid. No reflash. `python3 air96_cli.py screensaver on` does the same pulse while the Omarchy screensaver is running.
9. Open the Keys tab. The picture is the Air96 layout. Click a key, search a keycode, Apply, and confirm the key. The plugin never resets EEPROM.

The QML panel was not launched here. If the bar icon fails to load, the Python CLI still applies lighting and syncs the theme.

## Layout of the repo

| Path | Role |
| --- | --- |
| `manifest.json`, `Service.qml`, `Widget.qml`, `Air96Panel.qml`, `Editor.qml` | Omarchy service and bar panel |
| `air96_worker.py` | Long-running NDJSON process |
| `air96_cli.py` | `status`, `devices`, `sync`, `apply`, `screensaver`, `doctor`, `panel`, `ha-token`, `ha-test` |
| `air96_protocol.py`, `air96_hid.py`, `air96_layout.py` | VIA packets, hidraw discovery, 100-key map |
| `install.sh` | Theme-set hook, plugin link, worker restart, and uninstall |
| `udev/` | Seat ACL rules, not installed automatically |
| `hooks/theme-set.d/50-air96-sync` | Theme hook. `./install.sh` links it into `~/.config/omarchy/hooks/theme-set.d/` |
