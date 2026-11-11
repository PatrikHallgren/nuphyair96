import json
import unittest

import support  # noqa: F401
from air96_profiles import import_vscode_keybindings, load_profiles, match_profile, validate_profile


VSCODE = """
[
  {"key": "ctrl+shift+p", "command": "workbench.action.showCommands"},
  {"key": "ctrl+s", "command": "workbench.action.files.save"},
  {"key": "ctrl+k ctrl+s", "command": "workbench.action.openGlobalKeybindings"},
  {"key": "-ctrl+s", "command": "-workbench.action.files.save"},
  {"key": "ctrl+shift+f12", "command": "editor.action.unknownChord"},
  {"key": "ctrl+alt+shift+win+a", "command": "too.many"}
]
"""


class ProfileTests(unittest.TestCase):
    def test_shipped_examples_match_windows(self):
        profiles = load_profiles(shipped_dir=support.ROOT / "profiles")
        firefox = match_profile(profiles, "firefox", "Mozilla Firefox")
        self.assertEqual(firefox["id"], "firefox")
        self.assertIn("t", {item["key"] for item in firefox["keys"]})
        code = match_profile(profiles, "Cursor", "main.py - Cursor")
        self.assertEqual(code["id"], "code")
        game = match_profile(profiles, "Minecraft", "Minecraft 1.21")
        self.assertEqual(game["id"], "minecraft")
        self.assertIsNone(match_profile(profiles, "Alacritty", "shell"))

    def test_user_profile_overrides_shipped_id(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "firefox.json").write_text(json.dumps({
                "id": "firefox",
                "name": "Custom",
                "enabled": False,
                "match": {"class": ["firefox"]},
                "keys": [{"key": "t", "label": "Nope"}],
            }))
            profiles = load_profiles(user_dir=path, shipped_dir=support.ROOT / "profiles")
            self.assertIsNone(match_profile(profiles, "firefox", ""))
            self.assertTrue(any(item["id"] == "code" for item in profiles))

    def test_rejects_unknown_keys(self):
        with self.assertRaises(Exception):
            validate_profile({"id": "bad", "match": {"class": ["x"]}, "keys": [{"key": "not-a-key"}]})

    def test_vscode_import_keeps_the_first_chord(self):
        profile = import_vscode_keybindings(
            VSCODE, profile_id="vscode", name="VS Code", classes=["Code"])
        keys = {item["key"]: item for item in profile["keys"]}
        self.assertEqual(keys["p"]["mods"], ["ctrl", "shift"])
        self.assertEqual(keys["s"]["mods"], ["ctrl"])
        self.assertEqual(keys["f12"]["mods"], ["ctrl", "shift"])
        self.assertEqual(profile["match"]["class"], ["Code"])
        self.assertTrue(keys["p"]["label"])


if __name__ == "__main__":
    unittest.main()
