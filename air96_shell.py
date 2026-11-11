"""See whether the Omarchy bar has the Air96 widget, and ask it to open.

A third-party bar widget is on the bar only after its id is in shell.json.
Linking ~/.config/omarchy/plugins/local.nuphy-air96 is not enough. Omarchy
enables it with `omarchy plugin enable`, which places the widget in the
section named by the manifest (right). The icon's popup answers
`omarchy-shell air96 toggle` once that widget is loaded.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess

PLUGIN_ID = "local.nuphy-air96"
IPC_TARGET = "air96"
REQUIRED_FILES = (
    "manifest.json",
    "Widget.qml",
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
    """Ask the running shell to rescan and enable the widget. Returns report lines."""
    runner = runner or default_runner
    lines = []
    if not _which("omarchy-shell", runner) and not _which("omarchy", runner):
        lines.append("omarchy is not on PATH, so this command cannot register the bar icon.")
        lines.append("On the Omarchy machine, run these three lines:")
        lines.append("omarchy-shell shell rescanPlugins")
        lines.append(f"omarchy plugin enable {PLUGIN_ID} --yes")
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
        result = runner(["omarchy", "plugin", "enable", PLUGIN_ID, "--yes"], timeout=8)
        text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
        if result.returncode == 0:
            lines.append(f"Enabled {PLUGIN_ID}. A new bar widget is placed on the right.")
            return lines, True
        lines.append(f"omarchy plugin enable exited {result.returncode}. {text[:300]}".rstrip())
        lines.append(f"Run it in a terminal: omarchy plugin enable {PLUGIN_ID} --yes")
        return lines, False
    lines.append("The omarchy command is not on PATH. The shell was rescanned, but the icon was not enabled.")
    lines.append(f"omarchy plugin enable {PLUGIN_ID} --yes")
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
        "That target exists only after the icon is on the bar and the shell has loaded it.",
        "omarchy-restart-shell",
        "python3 air96_cli.py panel",
    ]
    return result.returncode or 1, lines


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
            lines.append(f"Enable it with: omarchy plugin enable {PLUGIN_ID} --yes")
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
                error_text = str(record.get("error") or record.get("loadError") or "")
                enabled = record.get("enabled")
                lines.append(
                    f"Shell sees {PLUGIN_ID}: enabled={enabled} error={error_text or 'none'}"
                )
                if error_text:
                    problems.append("The shell found the plugin but reported an error: " + error_text[:240])
                if enabled is False:
                    problems.append("The shell has the plugin and it is disabled.")
    else:
        lines.append("omarchy-shell is not on PATH, so this command cannot ask the bar what it loaded.")
    if not places and not enabled_now:
        problems.append("The bar layout does not list the Air96 widget, so no icon is drawn.")
    lines.append("Open the panel with: python3 air96_cli.py panel")
    lines.append(f"That runs: omarchy-shell {IPC_TARGET} toggle")
    if problems:
        lines.append("Not ready:")
        lines.extend(problems)
    else:
        lines.append("The plugin files are installed and the bar layout lists the widget.")
    return {"ok": not problems, "lines": lines, "problems": problems}
