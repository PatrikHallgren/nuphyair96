import unittest

import support  # noqa: F401
from air96_theme import color_from_theme_text, parse_colors_toml, read_theme_color


class ThemeTests(unittest.TestCase):
    def test_accent_from_colors_toml(self):
        text = '\n# comment\naccent = "#7aa2f7" # tokyo\nbackground = "#1a1b26"\n'
        self.assertEqual(parse_colors_toml(text)["accent"], "#7aa2f7")
        self.assertEqual(color_from_theme_text("", text), "#7aa2f7")

    def test_keyboard_rgb_without_hash_wins(self):
        # Tokyo Night ships keyboard.rgb as bare hex, and Omarchy keeps that file.
        self.assertEqual(color_from_theme_text("ff00ff\n", 'accent = "#7aa2f7"\n'), "#ff00ff")

    def test_keyboard_rgb_with_hash_and_blank_lines(self):
        self.assertEqual(color_from_theme_text("\n#ff8800\n", ""), "#ff8800")

    def test_comments_and_invalid_colors_are_ignored(self):
        self.assertEqual(color_from_theme_text("# this is a comment\nnope\n", "accent = \"red\"\n"), "")

    def test_single_quoted_accent(self):
        self.assertEqual(color_from_theme_text("", "accent = '#89b4fa'\n"), "#89b4fa")

    def test_read_theme_directory(self):
        from support import BackendCase
        case = BackendCase()
        case.setUp()
        try:
            (case.theme / "colors.toml").write_text('accent = "#9ece6a"\n')
            self.assertEqual(read_theme_color(case.theme), "#9ece6a")
            (case.theme / "keyboard.rgb").write_text("ff00ff\n")
            self.assertEqual(read_theme_color(case.theme), "#ff00ff")
        finally:
            case.tearDown()


if __name__ == "__main__":
    unittest.main()
