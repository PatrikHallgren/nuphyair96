"""See whether the Omarchy bar has the Air96 widget, and ask it to open.

A third-party bar widget is on the bar only after its id is in shell.json.
Linking ~/.config/omarchy/plugins/local.nuphy-air96 is not enough. Omarchy
places it with `omarchy plugin enable <id> --section right`. The next
argument is a bar section, not `--yes`. The icon's popup answers
`omarchy-shell air96 toggle` once that widget has been instantiated.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess

PLUGIN_ID = "local.nuphy-air96"
IPC_TARGET = "air96"
ENABLE_ARGV = ["omarchy", "plugin", "enable", PLUGIN_ID, "--section", "right"]
ENABLE_COMMAND = "omarchy plugin enable local.nuphy-air96 --section right"
JOURNAL_COMMAND = "journalctl --user -t omarchy-shell -n 200 --no-pager"
REQUIRED_FILES = (
    "manifest.json",
    "Widget.qml",
    "Air96Panel.qml",
    "Editor.qml",
    "Service.qml",
    "KeyboardView.qml",
    "ColorPicker.qml",
    "LightingSlider.qml",
    "PlainText.qml",
    "air96_worker.py",
)


def home_dir():
    return Path(os.environ.get("HOME") or Path.home())


def config_home():
    override = os.environ.get("XDG_CONFIG_HOME")
    return Path(override) if override else home_dir() / ".config"


def plugin_dir():
    return home_dir() / ".config" / "omarchy" / "plugins" / PLUGIN_ID


def shell_config_path():
    return config_home() / "omarchy" / "shell.json"


def _entry_id(entry):
    if isinstance(entry, dict):
        return str(entry.get("id") or "")
    if isinstance(entry, str):
        return entry
    return ""


def widget_places(config):
    """Sections of shell.json that name this plugin. Empty means the bar will not show it."""
    places = []
    if not isinstance(config, dict):
        return places
    bar = config.get("bar")
    layout = bar.get("layout") if isinstance(bar, dict) else None
    if isinstance(layout, dict):
        for section, entries in layout.items():
            if not isinstance(entries, list):
                continue
            if any(_entry_id(entry) == PLUGIN_ID for entry in entries):
                places.append(str(section))
    plugins = config.get("plugins")
    if isinstance(plugins, list) and any(_entry_id(entry) == PLUGIN_ID for entry in plugins):
        places.append("plugins")
    return places


def load_shell_config(path=None):
    path = Path(path) if path else shell_config_path()
    if not path.is_file():
        return None, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)[:200]
    if not isinstance(data, dict):
        return None, "shell.json is not an object"
    return data, ""


class CommandResult:
    def __init__(self, code, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def default_runner(argv, timeout=4):
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return CommandResult(124, out, err or "timed out")
    except OSError as exc:
        return CommandResult(127, "", str(exc))
    return completed


def plugin_from_list(payload):
    if isinstance(payload, dict):
        items = payload.get("plugins")
        if items is None:
            items = payload.get("items")
        if items is None and payload.get("id"):
            items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return None
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("id") == PLUGIN_ID:
            return item
    return None


def _which(name, runner):
    if runner is not default_runner:
        probe = runner(["sh", "-c", f"command -v {name}"], timeout=2)
        return probe.returncode == 0 and bool((probe.stdout or "").strip())
    return shutil.which(name) is not None


def register_with_shell(runner=None):
    """Ask the running shell to rescan and place the widget on the right."""
    runner = runner or default_runner
    lines = []
    if not _which("omarchy-shell", runner) and not _which("omarchy", runner):
        lines.append("omarchy is not on PATH, so this command cannot register the bar icon.")
        lines.append("On the Omarchy machine, run these three lines:")
        lines.append("omarchy-shell shell rescanPlugins")
        lines.append(ENABLE_COMMAND)
        lines.append("omarchy-restart-shell")
        return lines, False
    if _which("omarchy-shell", runner):
        result = runner(["omarchy-shell", "shell", "rescanPlugins"], timeout=6)
        text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
        if result.returncode == 0:
            lines.append("Rescanned plugins: " + (text or "ok"))
        else:
            lines.append(f"rescanPlugins exited {result.returncode}. {text[:240]}".rstrip())
            lines.append("If the shell is not running, start it with: omarchy-restart-shell")
    if _which("omarchy", runner):
        result = runner(ENABLE_ARGV, timeout=8)
        text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
        if result.returncode == 0:
            lines.append(f"Enabled {PLUGIN_ID} on the right.")
            lines.append("A shell that already loaded this plugin keeps the old QML until it restarts.")
            return lines, True
        lines.append(f"omarchy plugin enable exited {result.returncode}. {text[:300]}".rstrip())
        lines.append("Place it with: " + ENABLE_COMMAND)
        return lines, False
    lines.append("The omarchy command is not on PATH. The shell was rescanned, but the icon was not enabled.")
    lines.append(ENABLE_COMMAND)
    return lines, False


def open_panel(runner=None):
    """Toggle the bar popup. The widget has to be loaded or the target does not exist."""
    runner = runner or default_runner
    if not _which("omarchy-shell", runner):
        return 127, ["omarchy-shell is not on PATH, so the panel cannot be opened from here."]
    result = runner(["omarchy-shell", IPC_TARGET, "toggle"], timeout=6)
    text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
    if result.returncode == 0:
        return 0, [f"Asked the bar to toggle the Air96 panel ({IPC_TARGET}).", text or "ok"]
    lines = [
        f"omarchy-shell {IPC_TARGET} toggle exited {result.returncode}. {text[:300]}".rstrip(),
        "That target exists only after the bar has instantiated the widget.",
        "omarchy-restart-shell",
        "python3 air96_cli.py panel",
        "QML warnings, if the icon is still missing: " + JOURNAL_COMMAND,
    ]
    return result.returncode or 1, lines


def _mentions_plugin(line):
    low = line.lower()
    return any(token in low for token in (
        "local.nuphy-air96",
        "air96panel",
        "widget.qml",
        "plugin widget",
        "air96 editor",
        "air96 panel",
    ))


def shell_log_lines(runner):
    """QML warnings from the omarchy-shell journal tag, if journalctl can read it."""
    if not _which("journalctl", runner):
        return ["journalctl is not on PATH, so QML warnings were not read."]
    interesting = []
    saw_journal = False
    commands = (
        ["journalctl", "--user", "-t", "omarchy-shell", "-n", "200", "--no-pager", "-o", "cat"],
        ["journalctl", "-t", "omarchy-shell", "-n", "200", "--no-pager", "-o", "cat"],
    )
    for argv in commands:
        result = runner(argv, timeout=6)
        if result.returncode != 0:
            continue
        saw_journal = True
        for line in (result.stdout or "").splitlines():
            if _mentions_plugin(line):
                interesting.append(line.strip())
        if interesting:
            break
    if interesting:
        return ["Recent shell log lines for this plugin:"] + interesting[-8:]
    if saw_journal:
        return ["No recent omarchy-shell journal line mentions this plugin."]
    return ["Could not read the omarchy-shell journal. Try: " + JOURNAL_COMMAND]


def geometry_report(payload):
    """Lines and problems from `omarchy-shell shell debugBarGeometry`."""
    if isinstance(payload, dict):
        slots = payload.get("slots")
        if slots is None:
            slots = payload.get("items")
        payload = slots
    if not isinstance(payload, list):
        return ["debugBarGeometry was not a list."], []
    records = [
        item for item in payload
        if isinstance(item, dict) and str(item.get("id") or "") == PLUGIN_ID
    ]
    if not records:
        return [], [
            "Bar geometry has no " + PLUGIN_ID + " slot. The widget QML was not instantiated.",
        ]
    lines = []
    shown = False
    for record in records:
        width = int(record.get("itemWidth") or 0)
        height = int(record.get("itemHeight") or 0)
        visible = record.get("visible")
        item_visible = record.get("itemVisible")
        lines.append(
            "Bar slot {section}: width={slot_width} height={slot_height} "
            "visible={visible} itemVisible={item_visible} itemWidth={width} itemHeight={height}".format(
                section=record.get("section") or "?",
                slot_width=record.get("width"),
                slot_height=record.get("height"),
                visible=visible,
                item_visible=item_visible,
                width=width,
                height=height,
            )
        )
        if width > 0 and height > 0 and visible is not False and item_visible is not False:
            shown = True
    problems = []
    if not shown:
        problems.append(
            "The Air96 slot is on the bar but its rendered size is 0 or it is not visible."
        )
    return lines, problems


def doctor(register=False, runner=None):
    """Plain lines about the plugin files and whether the bar lists the widget."""
    runner = runner or default_runner
    lines = []
    problems = []
    directory = plugin_dir()
    lines.append(f"Plugin directory: {directory}")
    if directory.is_symlink():
        try:
            lines.append(f"Link target: {directory.resolve()}")
        except OSError as exc:
            problems.append(f"The plugin link does not resolve: {exc}")
    elif directory.is_dir():
        lines.append("The plugin path is a real directory, not a link to this checkout.")
    else:
        problems.append("The plugin directory is missing. ./install.sh creates the link.")
    for name in REQUIRED_FILES:
        path = directory / name
        if path.is_file():
            lines.append(f"{name}: present")
        else:
            problems.append(f"{name}: missing from the plugin directory")
    enabled_now = False
    if register:
        registered_lines, enabled_now = register_with_shell(runner)
        lines.extend(registered_lines)
    config_path = shell_config_path()
    lines.append(f"shell.json: {config_path}")
    config, error = load_shell_config(config_path)
    places = []
    if error:
        problems.append(f"shell.json could not be read: {error}")
    elif config is None:
        lines.append("shell.json is absent. Omarchy is using its built-in bar until a plugin is enabled.")
        lines.append("Enabling writes the widget into the bar layout. Do not hand-write a partial shell.json.")
    else:
        places = widget_places(config)
        if places:
            lines.append("Bar layout lists " + PLUGIN_ID + " in: " + ", ".join(places))
        else:
            lines.append(f"shell.json does not list {PLUGIN_ID}.")
            lines.append("Enable it with: " + ENABLE_COMMAND)
    if _which("omarchy-shell", runner):
        ping = runner(["omarchy-shell", "shell", "ping"], timeout=4)
        ping_text = ((ping.stdout or "") + " " + (ping.stderr or "")).strip()
        if ping.returncode == 0:
            lines.append("Shell ping: " + (ping_text or "ok"))
        else:
            problems.append(f"The shell did not answer ping ({ping.returncode}). {ping_text[:200]}".rstrip())
            lines.append("Restart it with: omarchy-restart-shell")
        listed = runner(["omarchy-shell", "shell", "listPlugins"], timeout=4)
        raw = (listed.stdout or "").strip()
        if listed.returncode != 0:
            problems.append(f"listPlugins exited {listed.returncode}. {(listed.stderr or '')[:200]}".rstrip())
        elif not raw:
            problems.append("listPlugins returned nothing. The shell has not discovered the plugin directory.")
        else:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                lines.append("listPlugins was not JSON. First line: " + raw.splitlines()[0][:200])
                payload = None
            record = plugin_from_list(payload) if payload is not None else None
            if record is None and payload is not None:
                problems.append("listPlugins does not include " + PLUGIN_ID + ".")
            elif record is not None:
                enabled = record.get("enabled")
                lines.append(
                    f"Shell sees {PLUGIN_ID}: enabled={enabled}. "
                    "listPlugins does not report QML load errors."
                )
                if enabled is False:
                    problems.append("The shell has the plugin and it is not in the bar layout.")
        geometry = runner(["omarchy-shell", "shell", "debugBarGeometry"], timeout=4)
        raw_geometry = (geometry.stdout or "").strip()
        if geometry.returncode != 0:
            problems.append(
                f"debugBarGeometry exited {geometry.returncode}. "
                f"{(geometry.stderr or '')[:200]}".rstrip()
            )
        elif not raw_geometry:
            problems.append("debugBarGeometry returned nothing.")
        else:
            try:
                geometry_payload = json.loads(raw_geometry)
            except json.JSONDecodeError:
                lines.append("debugBarGeometry was not JSON. First line: " + raw_geometry.splitlines()[0][:200])
                geometry_payload = None
            if geometry_payload is not None:
                geometry_lines, geometry_problems = geometry_report(geometry_payload)
                lines.extend(geometry_lines)
                problems.extend(geometry_problems)
        lines.extend(shell_log_lines(runner))
    else:
        lines.append("omarchy-shell is not on PATH, so this command cannot ask the bar what it loaded.")
    if not places and not enabled_now:
        problems.append("The bar layout does not list the Air96 widget, so no icon is drawn.")
    lines.append("Open the panel with: python3 air96_cli.py panel")
    lines.append(f"That runs: omarchy-shell {IPC_TARGET} toggle")
    lines.append("QML warnings, if the icon is still missing: " + JOURNAL_COMMAND)
    if problems:
        lines.append("Not ready:")
        lines.extend(problems)
    else:
        lines.append("The plugin files are installed and the bar layout lists the widget.")
    return {"ok": not problems, "lines": lines, "problems": problems}
