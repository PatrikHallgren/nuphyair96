import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from air96_shell import REQUIRED_FILES, CommandResult, doctor, open_panel, widget_places


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write_plugin(self):
        plugin = self.home / ".config/omarchy/plugins/local.nuphy-air96"
        plugin.mkdir(parents=True)
        for name in REQUIRED_FILES:
            (plugin / name).write_text("ok\n")
        return plugin

    def test_missing_plugin_is_not_ready(self):
        report = doctor()
        self.assertFalse(report["ok"])
        text = "\n".join(report["lines"])
        self.assertIn("missing", text.lower())
        self.assertIn("python3 air96_cli.py panel", text)

    def test_shell_json_on_the_right_is_ready_without_a_running_shell(self):
        self.write_plugin()
        shell = self.home / ".config/omarchy/shell.json"
        shell.parent.mkdir(parents=True, exist_ok=True)
        shell.write_text(json.dumps({
            "version": 1,
            "bar": {"layout": {"right": [{"id": "local.nuphy-air96"}], "left": [{"id": "omarchy.menu"}]}},
        }))
        report = doctor()
        self.assertTrue(report["ok"], "\n".join(report["lines"]))
        self.assertIn("right", "\n".join(report["lines"]))

    def test_register_enables_the_plugin_and_panel_toggles_it(self):
        self.write_plugin()
        calls = []

        def runner(argv, timeout=4):
            calls.append(list(argv))
            if argv[:2] == ["sh", "-c"]:
                return CommandResult(0, "/usr/bin/" + argv[2].split()[-1] + "\n")
            if argv[:3] == ["omarchy", "plugin", "enable"]:
                shell = self.home / ".config/omarchy/shell.json"
                shell.parent.mkdir(parents=True, exist_ok=True)
                shell.write_text(json.dumps({
                    "version": 1,
                    "bar": {"layout": {"right": [{"id": "local.nuphy-air96"}]}},
                }))
                return CommandResult(0, "enabled\n")
            if argv[-1] == "listPlugins":
                return CommandResult(0, json.dumps([{"id": "local.nuphy-air96", "enabled": True}]))
            if argv[-1] == "toggle":
                return CommandResult(0, "ok\n")
            return CommandResult(0, "ok\n")

        report = doctor(register=True, runner=runner)
        text = "\n".join(report["lines"])
        self.assertTrue(report["ok"], text)
        self.assertIn(["omarchy-shell", "shell", "rescanPlugins"], calls)
        self.assertIn(["omarchy", "plugin", "enable", "local.nuphy-air96", "--yes"], calls)
        self.assertIn("enabled=True", text)
        code, lines = open_panel(runner)
        self.assertEqual(code, 0, lines)
        self.assertIn(["omarchy-shell", "air96", "toggle"], calls)

    def test_places_include_a_string_entry(self):
        places = widget_places({"bar": {"layout": {"tray": ["local.nuphy-air96"]}}})
        self.assertEqual(places, ["tray"])
