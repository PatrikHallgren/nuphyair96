import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import support  # noqa: F401
from air96_backend import Backend
from air96_cli import main
from support import ROOT, FakeKeyboard


VSCODE = '[{"key": "ctrl+s", "command": "workbench.action.files.save"}]\n'


class RecordingTransport:
    def __init__(self, keyboard):
        self.keyboard = keyboard
        self.closed = False

    def close(self):
        self.closed = True

    def transact(self, payload):
        return self.keyboard.transact(payload)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.theme = self.root / "theme"
        self.theme.mkdir()
        (self.theme / "keyboard.rgb").write_text("ff00ff\n")
        self.keyboard = FakeKeyboard()
        self.node = self.root / "hidraw0"
        self.node.write_bytes(b"")
        self.device = {
            "path": str(self.node),
            "vid": 0x19F5,
            "pid": 0x3265,
            "name": "NuPhy Air96 V2",
            "iface": 1,
        }

    def tearDown(self):
        self.temp.cleanup()

    def backend(self):
        return Backend(
            config_path=self.root / "config.json",
            state_dir=self.root / "state",
            theme_path=self.theme,
            profiles_dir=self.root / "profiles",
            environ={},
        )

    def transport(self, path, timeout=0.4):
        return RecordingTransport(self.keyboard)

    def run_main(self, argv, devices=None):
        stdout = StringIO()
        stderr = StringIO()
        found = [] if devices is None else devices
        with patch("air96_cli.Backend", self.backend), patch("air96_worker.find_devices", return_value=found), patch(
            "air96_worker.HidTransport", self.transport
        ), patch("air96_hid.find_devices", return_value=found), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_help_and_the_script_entry_point(self):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        text = stdout.getvalue()
        for name in ("status", "devices", "sync", "apply", "import-vscode", "music"):
            self.assertIn(name, text)
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as missing:
                main([])
        self.assertEqual(missing.exception.code, 2)
        script = subprocess.run(
            [sys.executable, str(ROOT / "air96_cli.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(script.returncode, 0, script.stderr)
        self.assertIn("import-vscode", script.stdout)
        bare = subprocess.run(
            [sys.executable, str(ROOT / "air96_cli.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(bare.returncode, 2)
        self.assertNotIn("AttributeError", bare.stderr)

    def test_devices_status_sync_and_apply_parse(self):
        code, out, err = self.run_main(["devices"], devices=[self.device])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), [self.device])

        code, out, err = self.run_main(["status"])
        self.assertEqual(code, 0, err)
        status = json.loads(out)
        self.assertFalse(status["connected"])
        self.assertEqual(status["setupIssue"], "not-found")
        self.assertNotIn("token", status["homeAssistant"])

        code, out, err = self.run_main(["sync"])
        self.assertEqual(code, 0, err)
        self.assertIn("off", out.lower())

        code, out, err = self.run_main(
            ["apply", "--hex", "#112233", "--effect", "1", "--brightness", "20", "--speed", "30", "--follow", "false"],
            devices=[self.device],
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Backlight", out)
        self.assertEqual(self.keyboard.effect, 1)
        self.assertEqual(self.keyboard.brightness, 20)
        self.assertEqual(self.keyboard.saved, 1)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertEqual(saved["lighting"]["hex"], "#112233")
        self.assertFalse(saved["lighting"]["follow_theme"])

    def test_apply_without_a_keyboard_exits_instead_of_crashing(self):
        code, _out, err = self.run_main(["apply", "--hex", "#abcdef", "--follow", "true"])
        self.assertEqual(code, 1)
        self.assertIn("not connected", err.lower())

    def test_import_vscode_from_a_file_and_stdin(self):
        path = self.root / "keybindings.json"
        path.write_text(VSCODE)
        code, out, err = self.run_main(["import-vscode", str(path), "--id", "editor", "--name", "Editor"])
        self.assertEqual(code, 0, err)
        profile = json.loads(out)
        self.assertEqual(profile["id"], "editor")
        self.assertEqual(profile["keys"][0]["key"], "s")
        with patch("sys.stdin", StringIO(VSCODE)):
            code, out, err = self.run_main(["import-vscode", "-"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["keys"][0]["mods"], ["ctrl"])

    def test_music_toggle_saves_without_opening_a_keyboard(self):
        code, out, err = self.run_main(["music", "on", "--effect", "vu"])
        self.assertEqual(code, 0, err)
        self.assertIn("Music", out)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertTrue(saved["music"]["enabled"])
        self.assertEqual(saved["music"]["effect"], "vu")
        code, out, err = self.run_main(["music", "off"])
        self.assertEqual(code, 0, err)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertFalse(saved["music"]["enabled"])
        self.assertEqual(saved["music"]["effect"], "vu")


if __name__ == "__main__":
    unittest.main()
