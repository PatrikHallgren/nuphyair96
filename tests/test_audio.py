import math
import unittest

from air96_audio import analyze, frame_colors, via_pulse
from air96_layout import KEYS


def tone(frequency, amplitude=0.8, count=512, rate=16000):
    return [amplitude * math.sin(2 * math.pi * frequency * index / rate) for index in range(count)]


class AudioTests(unittest.TestCase):
    def test_a_low_tone_peaks_left_of_a_high_tone(self):
        low = analyze(tone(80))["bands"]
        high = analyze(tone(4000))["bands"]
        self.assertLess(low.index(max(low)), high.index(max(high)))
        self.assertLess(analyze([0.0] * 512)["rms"], analyze(tone(440))["rms"])

    def test_spectrum_follows_columns_and_vu_is_flat(self):
        bands = [0.0] * 16
        bands[0] = 1.0
        colors = frame_colors({"rms": 1.0, "bands": bands}, "spectrum", "#ff0000")
        left = min(KEYS, key=lambda key: key["x"])
        right = max(KEYS, key=lambda key: key["x"] + key["w"])
        self.assertGreater(colors[left["led"]][0], 200)
        self.assertLess(colors[right["led"]][0], 40)
        flat = frame_colors({"rms": 0.0, "bands": [1.0, 0.0]}, "vu", "#ffffff")
        lit = [color for color in flat if color != (0, 0, 0)]
        self.assertTrue(lit)
        self.assertEqual(len(set(lit)), 1)
        self.assertEqual(flat[100], (0, 0, 0))

    def test_via_pulse_tracks_level_inside_a_byte(self):
        quiet = via_pulse({"rms": 0, "bands": [0] * 16}, "#3366ff", 200)
        loud = via_pulse({"rms": 1, "bands": [1] * 16}, "#3366ff", 200)
        self.assertLess(quiet["brightness"], loud["brightness"])
        self.assertGreaterEqual(quiet["brightness"], 8)
        self.assertLessEqual(loud["brightness"], 255)
        self.assertEqual(loud["effect"], 1)
        self.assertIsInstance(loud["hue"], int)
        self.assertIsInstance(loud["sat"], int)


if __name__ == "__main__":
    unittest.main()