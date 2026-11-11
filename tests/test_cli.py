import json
from pathlib import Path
import pty
import os
import stat
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
from air96_ha import HomeAssistantError
from air96_hid import HidError, HidTransport, set_debug
from air96_protocol import protocol_version_request
from support import ROOT, FakeKeyboard


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
        for name in ("status", "devices", "sync", "apply", "screensaver", "ha-token", "ha-test"):
            self.assertIn(name, text)
        self.assertIn("--debug", text)
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
        self.assertIn("screensaver", script.stdout)
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
        self.assertEqual(code, 1, err)
        self.assertIn("not connected", (out + err).lower())

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

    def test_screensaver_toggle_saves_without_opening_a_keyboard(self):
        code, out, err = self.run_main(["screensaver", "on"])
        self.assertEqual(code, 0, err)
        self.assertIn("Screensaver", out)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertTrue(saved["screensaver"]["enabled"])
        code, out, err = self.run_main(["screensaver", "off"])
        self.assertEqual(code, 0, err)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertFalse(saved["screensaver"]["enabled"])

    def test_ha_token_sanitizes_and_ha_test_reports_status(self):
        secret = "long-lived-token-value"
        setup = self.backend()
        setup.update_settings({"home_assistant": {
            "url": "http://ha.example",
            "entities": ["light.desk"],
        }})
        pasted = "\x1b[200~" + secret + "\x1b[201~\n"
        with patch("air96_cli.getpass.getpass", return_value=pasted):
            code, out, err = self.run_main(["ha-token"])
        self.assertEqual(code, 0, err)
        self.assertNotIn(secret, out + err)
        saved = json.loads((self.root / "config.json").read_text())
        path = Path(saved["home_assistant"]["token_file"])
        self.assertEqual(path.read_text(), secret + "\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(saved["home_assistant"]["token"], "")

        def fake_send(prepared, opener=None, timeout=5):
            if prepared["method"] == "GET":
                return {"status": 200, "body": json.dumps({"state": "on", "entity_id": "light.desk"})}
            self.assertEqual(prepared["headers"]["Authorization"], "Bearer " + secret)
            body = json.loads(prepared["body"])
            self.assertNotIn("brightness", body)
            self.assertNotIn(secret, prepared["body"].decode())
            return {"status": 200, "body": "[]"}

        with patch("air96_backend.send_ha", fake_send):
            code, out, err = self.run_main(["ha-test"])
        self.assertEqual(code, 0, err)
        self.assertIn("HTTP 200", out)
        self.assertNotIn(secret, out + err)

        with patch("air96_backend.send_ha", side_effect=HomeAssistantError("Home Assistant returned HTTP 401")):
            code, out, err = self.run_main(["ha-test"])
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", err)
        self.assertNotIn(secret, out + err)

        junk = "UNIQUESECRETVALUE is not a single token"
        with patch("air96_cli.getpass.getpass", return_value=junk):
            code, out, err = self.run_main(["ha-token"])
        self.assertEqual(code, 1)
        self.assertIn("malformed", err)
        self.assertNotIn("UNIQUESECRETVALUE", out + err)
        self.assertEqual(path.read_text(), secret + "\n")

    def test_debug_prints_the_report_when_the_keyboard_does_not_answer(self):
        set_debug(False)
        code, out, err = self.run_main(["--debug", "devices"])
        self.assertEqual(code, 0, err)
        import air96_hid
        self.assertTrue(air96_hid.debug)
        set_debug(False)
        master, slave = pty.openpty()
        try:
            transport = HidTransport(os.ttyname(slave), timeout=0.05)
            set_debug(True)
            stderr = StringIO()
            with redirect_stderr(stderr):
                with self.assertRaises(HidError) as raised:
                    transport.transact(protocol_version_request())
            message = str(raised.exception)
            trace = stderr.getvalue()
            sent = protocol_version_request().hex()
            self.assertIn(sent, message)
            self.assertIn("timed out", message)
            self.assertIn(sent, trace)
            self.assertIn("no report", trace)
            transport.close()
        finally:
            set_debug(False)
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
