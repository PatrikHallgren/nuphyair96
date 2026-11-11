import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest

from support import ROOT


HOOK = ROOT / "hooks" / "theme-set.d" / "50-air96-sync"
INSTALL = ROOT / "install.sh"


def fake_cli(path):
    path.write_text(textwrap.dedent("""\
        import os, sys
        from pathlib import Path
        Path(os.environ["AIR96_TEST_LOG"]).write_text(" ".join(sys.argv[1:]) + "\\n")
    """))


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["XDG_CONFIG_HOME"] = str(self.home / ".config")
        self.env.pop("AIR96_CLI", None)

    def tearDown(self):
        self.temp.cleanup()

    def run_install(self, *args):
        result = subprocess.run(
            [str(INSTALL), *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_hook_only_records_the_cli_and_uninstall_removes_it(self):
        result = self.run_install("--no-plugin")
        hook = self.home / ".config/omarchy/hooks/theme-set.d/50-air96-sync"
        recorded = self.home / ".config/omarchy-nuphy-air96/cli-path"
        self.assertTrue(hook.is_symlink())
        self.assertEqual(hook.resolve(), HOOK.resolve())
        self.assertEqual(recorded.read_text().strip(), str(ROOT / "air96_cli.py"))
        self.assertIn("Theme hook:", result.stdout)
        self.assertFalse((self.home / ".config/omarchy/plugins/local.nuphy-air96").exists())

        removed = self.run_install("--uninstall")
        self.assertFalse(hook.exists())
        self.assertFalse(recorded.exists())
        self.assertIn("Kept", removed.stdout)

    def test_plugin_link_replaces_a_copied_plugin_directory(self):
        result = self.run_install("--plugin")
        link = self.home / ".config/omarchy/plugins/local.nuphy-air96"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), ROOT.resolve())
        self.assertIn("Registering the bar widget", result.stdout)
        self.assertIn("not on PATH", result.stdout)

        self.run_install("--uninstall")
        self.assertFalse(link.exists())

        plugin = self.home / ".config/omarchy/plugins/local.nuphy-air96"
        plugin.mkdir(parents=True)
        (plugin / "air96_cli.py").write_text("# real clone\n")
        replaced = self.run_install("--plugin")
        self.assertTrue(plugin.is_symlink())
        self.assertEqual(plugin.resolve(), ROOT.resolve())
        backup = self.home / ".config/omarchy/plugins/local.nuphy-air96.previous"
        self.assertEqual((backup / "air96_cli.py").read_text(), "# real clone\n")
        self.assertIn("Replaced the separate plugin copy", replaced.stdout)
        self.run_install("--uninstall")
        self.assertFalse(plugin.exists())
        self.assertTrue(backup.is_dir())

    def test_hook_runs_sync_from_the_recorded_cli_without_a_plugin(self):
        log = Path(self.temp.name) / "log"
        cli = Path(self.temp.name) / "air96_cli.py"
        fake_cli(cli)
        self.env["AIR96_TEST_LOG"] = str(log)
        self.env["AIR96_CLI"] = str(cli)
        result = subprocess.run(
            ["bash", str(HOOK), "tokyo-night"],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text().strip(), "sync")
        self.assertNotIn("tokyo-night", log.read_text())

        del self.env["AIR96_CLI"]
        log.write_text("")
        path_file = self.home / ".config/omarchy-nuphy-air96/cli-path"
        path_file.parent.mkdir(parents=True, exist_ok=True)
        path_file.write_text(str(cli) + "\n")
        recorded = subprocess.run(
            ["bash", str(HOOK), "kanagawa"],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(log.read_text().strip(), "sync")

    def test_hook_finds_a_plugin_checkout_and_exits_quietly_when_missing(self):
        log = Path(self.temp.name) / "plugin-log"
        plugin = self.home / ".config/omarchy/plugins/local.nuphy-air96"
        plugin.mkdir(parents=True)
        fake_cli(plugin / "air96_cli.py")
        self.env["AIR96_TEST_LOG"] = str(log)
        copied = Path(self.temp.name) / "50-air96-sync"
        copied.write_text(HOOK.read_text())
        copied.chmod(copied.stat().st_mode | stat.S_IEXEC)
        result = subprocess.run(
            ["bash", str(copied), "everforest"],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text().strip(), "sync")

        empty = Path(self.temp.name) / "empty-home"
        empty.mkdir()
        missing = subprocess.run(
            ["bash", str(copied), "everforest"],
            env={**self.env, "HOME": str(Path(self.temp.name) / "empty-home"), "XDG_CONFIG_HOME": str(Path(self.temp.name) / "empty-home/.config")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(missing.returncode, 0)
        self.assertIn("not found", missing.stderr.lower())


if __name__ == "__main__":
    unittest.main()
