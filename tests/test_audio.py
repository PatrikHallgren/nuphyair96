import math
import unittest

from air96_audio import (
    Envelope, MonitorCapture, analyze, frame_colors, pipewire_monitor_target,
    recorder_command, via_pulse,
)
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
        flat = frame_colors({"rms": 0.5, "bands": [1.0, 0.0]}, "vu", "#ffffff")
        lit = [color for color in flat if color != (0, 0, 0)]
        self.assertTrue(lit)
        self.assertEqual(len(set(lit)), 1)
        self.assertEqual(flat[100], (0, 0, 0))
        dark = frame_colors({"rms": 0.0, "bands": [1.0]}, "vu", "#ffffff")
        self.assertEqual(dark[0], (0, 0, 0))

    def test_gate_decay_and_bass_pulse(self):
        gated = Envelope()
        noise = gated.update({"rms": 0.001, "bands": [1.0] * 16})
        self.assertTrue(noise["silent"])
        self.assertLess(max(noise["bands"]), 0.05)

        quiet = Envelope()
        settled = None
        for _ in range(40):
            settled = quiet.update({"rms": 0.04, "bands": [0.04] + [0.0] * 15})
        loud_env = Envelope()
        loud = None
        for _ in range(8):
            loud = loud_env.update({"rms": 0.5, "bands": [0.9] + [0.0] * 15})
        self.assertGreater(settled["bands"][0], 0.1)
        self.assertLess(settled["bands"][0], loud["bands"][0])

        beat = Envelope()
        hit = beat.update({"rms": 0.5, "bands": [0.9] + [0.0] * 15})
        later = hit
        for _ in range(12):
            later = beat.update({"rms": 0.03, "bands": [0.02] + [0.0] * 15})
        self.assertGreater(hit["bands"][0], 0.4)
        self.assertLess(later["bands"][0], hit["bands"][0] * 0.5)

    def test_a_tone_is_a_peak_not_a_left_to_right_ramp(self):
        low = analyze(tone(90, amplitude=0.5))
        high = analyze(tone(3000, amplitude=0.5))
        self.assertGreater(max(low["bands"][:6]), max(low["bands"][-4:]) * 4)
        self.assertGreater(max(high["bands"][-4:]), max(high["bands"][:6]) * 4)
        env = Envelope()
        levels = None
        for _ in range(12):
            levels = env.update(low)
        colors = frame_colors(levels, "spectrum", "#ffffff")
        left = min(KEYS, key=lambda key: key["x"])
        right = max(KEYS, key=lambda key: key["x"] + key["w"])
        self.assertGreater(colors[left["led"]][0], 80)
        self.assertLess(colors[right["led"]][0], 25)

    def test_recorder_targets_the_speaker_monitor_not_the_microphone(self):
        def which(name):
            if name in ("parecord", "pw-record"):
                return "/usr/bin/" + name
            return None

        command = recorder_command(which)
        self.assertEqual(command[0], "parecord")
        self.assertIn("--device=@DEFAULT_MONITOR@", command)
        joined = " ".join(command)
        self.assertNotIn("DEFAULT_SOURCE", joined)
        self.assertNotIn("@DEFAULT_AUDIO_SINK@.monitor", joined)

        fallback = recorder_command(
            lambda name: "/usr/bin/pw-record" if name == "pw-record" else None,
            resolve_monitor=lambda: "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
        )
        self.assertEqual(fallback[0], "pw-record")
        self.assertIn("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor", fallback)
        self.assertIsNone(recorder_command(
            lambda name: "/usr/bin/pw-record" if name == "pw-record" else None,
            resolve_monitor=lambda: None,
        ))

        class Result:
            returncode = 0
            stdout = b"alsa_output.pci-0000_00_1f.3.analog-stereo\n"

        self.assertEqual(
            pipewire_monitor_target(run=lambda *_args, **_kwargs: Result()),
            "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
        )

    def test_a_stalled_recorder_does_not_reuse_the_last_window(self):
        class Stream:
            def __init__(self, chunks):
                self.chunks = list(chunks)

            def fileno(self):
                return -1

            def read_one(self):
                if not self.chunks:
                    return b""
                return self.chunks.pop(0)

        class Proc:
            def __init__(self):
                self.stdout = Stream([b"\x10\x00" * 600])
                self.stderr = Stream([])
                self.returncode = None

            def poll(self):
                return self.returncode

        capture = MonitorCapture()
        capture.proc = Proc()
        capture._drain = lambda stream: stream.read_one() if stream is not None else b""
        first = capture.read_samples()
        self.assertIsNotNone(first)
        self.assertFalse(capture.stalled)
        for _ in range(7):
            self.assertIsNotNone(capture.read_samples())
        self.assertIsNone(capture.read_samples())
        self.assertTrue(capture.stalled)
        self.assertGreater(capture.bytes_total, 0)

        colors = frame_colors({"rms": 0.2, "bands": [0.05] * 16, "bass": 1.0}, "spectrum", "#ff0000")
        left = min(KEYS, key=lambda key: key["x"])
        right = max(KEYS, key=lambda key: key["x"] + key["w"])
        self.assertGreater(colors[left["led"]][0], colors[right["led"]][0] + 80)

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