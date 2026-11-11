"""Music-reactive colors for the Air96.

The idea of streaming a per-key visualizer, and the 9-LED batch layout it
rides on, comes from ravila4/nuphy-rgb-music by Ricardo Avila (MIT). This
file does not use that project's audio code. Capture is PipeWire or
PulseAudio, and the transform is a small radix-2 FFT in the standard library.
"""

import math
import os
import shutil
import subprocess

from air96_layout import KEYS, LED_COUNT
from air96_protocol import hex_to_rgb, rgb_to_qmk_hsv

RATE = 16000
WINDOW = 512
BANDS = 16


def pcm_s16le(blob):
    count = len(blob) // 2
    samples = []
    for index in range(count):
        start = index * 2
        samples.append(int.from_bytes(blob[start:start + 2], "little", signed=True) / 32768.0)
    return samples


def rms(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _fft(samples):
    size = 1
    while size < len(samples):
        size *= 2
    if size > 2048:
        samples = samples[-2048:]
        size = 2048
    real = [float(sample) for sample in samples]
    real.extend(0.0 for _ in range(size - len(real)))
    imag = [0.0] * size
    reverse = 0
    for index in range(1, size):
        bit = size >> 1
        while reverse & bit:
            reverse ^= bit
            bit >>= 1
        reverse ^= bit
        if index < reverse:
            real[index], real[reverse] = real[reverse], real[index]
            imag[index], imag[reverse] = imag[reverse], imag[index]
    length = 2
    while length <= size:
        angle = 2 * math.pi / length
        step_real = math.cos(angle)
        step_imag = -math.sin(angle)
        for start in range(0, size, length):
            twiddle_real = 1.0
            twiddle_imag = 0.0
            half = length // 2
            for offset in range(half):
                left = start + offset
                right = left + half
                mixed_real = twiddle_real * real[right] - twiddle_imag * imag[right]
                mixed_imag = twiddle_real * imag[right] + twiddle_imag * real[right]
                real[right] = real[left] - mixed_real
                imag[right] = imag[left] - mixed_imag
                real[left] += mixed_real
                imag[left] += mixed_imag
                next_real = twiddle_real * step_real - twiddle_imag * step_imag
                twiddle_imag = twiddle_real * step_imag + twiddle_imag * step_real
                twiddle_real = next_real
        length *= 2
    return [math.hypot(real[index], imag[index]) / size for index in range(size // 2)]


def _band_edges(rate, count):
    low = 40.0
    high = min(rate / 2.0, 7500.0)
    span = math.log(high / low)
    return [low * math.exp(span * index / count) for index in range(count + 1)]


def analyze(samples, rate=RATE, bands=BANDS):
    window = list(samples[-WINDOW:])
    magnitudes = _fft(window) if window else []
    size = len(magnitudes) * 2 or 1
    edges = _band_edges(rate, bands)
    values = []
    for index in range(bands):
        start = edges[index]
        end = edges[index + 1]
        energy = 0.0
        bins = 0
        for bin_index, magnitude in enumerate(magnitudes):
            frequency = bin_index * rate / size
            if frequency < start or frequency >= end:
                continue
            energy += magnitude
            bins += 1
        values.append(energy / bins if bins else 0.0)
    # Leave the bands in absolute units. Dividing by this frame's peak makes
    # silence and a kick the same shape, so the lights never look like music.
    level = min(1.0, rms(window))
    bass = sum(values[:3]) / 3 if values else 0.0
    highs = sum(values[-3:]) / 3 if values else 0.0
    return {"rms": level, "bands": values, "bass": bass, "highs": highs}


class Envelope:
    """Fast attack, slow decay, a noise gate, and a slow loudness follower.

    nuphy-rgb-music decays each frame (about 0.97 at 30 fps) so a beat has a
    tail. This HID path cannot repaint every LED that often, so the tail is
    a bit faster and the picture only sends the LEDs that moved.
    """

    def __init__(self, attack=0.65, decay=0.88, open_at=0.018, close_at=0.010):
        self.attack = attack
        self.decay = decay
        self.open_at = open_at
        self.close_at = close_at
        self.gain = 0.05
        self.open = False
        self.level = 0.0
        self.bands = [0.0] * BANDS

    def update(self, raw):
        rms_level = float(raw.get("rms") or 0.0)
        if self.open:
            self.open = rms_level >= self.close_at
        else:
            self.open = rms_level >= self.open_at
        incoming = [float(value) for value in (raw.get("bands") or [])]
        if len(incoming) < BANDS:
            incoming.extend(0.0 for _ in range(BANDS - len(incoming)))
        incoming = incoming[:BANDS]
        if not self.open:
            incoming = [0.0] * BANDS
            peak = 0.0
        else:
            peak = max(incoming) if incoming else 0.0
            if peak > self.gain:
                self.gain = self.gain * 0.6 + peak * 0.4
            else:
                self.gain = self.gain * 0.995 + peak * 0.005
            self.gain = max(self.gain, 1e-4)
        target = [min(1.0, value / self.gain) for value in incoming] if self.open else [0.0] * BANDS
        rising = (max(target) if target else 0.0) >= self.level
        keep = (1.0 - self.attack) if rising else self.decay
        take = 1.0 - keep
        blended = [old * keep + new * take for old, new in zip(self.bands, target)]
        self.bands = blended
        self.level = max(blended) if blended else 0.0
        return {
            "rms": 0.0 if not self.open and self.level < 0.04 else min(1.0, max(self.level, rms_level if self.open else 0.0)),
            "bands": blended,
            "bass": sum(blended[:3]) / 3,
            "highs": sum(blended[-3:]) / 3,
            "silent": (not self.open) and self.level < 0.04,
        }


def _tint(color, scale):
    red, green, blue = hex_to_rgb(color)
    amount = max(0.0, min(1.0, scale))
    return tuple(max(0, min(255, round(channel * amount))) for channel in (red, green, blue))


def frame_colors(levels, effect, tint, keys=None):
    """Per-key RGB for one music frame. Side LEDs stay off."""
    keys = KEYS if keys is None else keys
    colors = [(0, 0, 0)] * LED_COUNT
    bands = list(levels.get("bands") or [])
    if effect == "vu" or not bands:
        scale = 0.92 * float(levels.get("rms") or 0)
        color = _tint(tint, scale)
        for key in keys:
            colors[key["led"]] = color
        return colors
    span = max(key["x"] + key["w"] for key in keys)
    last = len(bands) - 1
    bass = max(0.0, min(1.0, float(levels.get("bass") or 0.0)))
    for key in keys:
        center = key["x"] + key["w"] / 2
        index = min(last, int(center / span * len(bands)))
        amount = bands[index]
        if center < span * 0.28:
            amount = max(amount, bass)
        colors[key["led"]] = _tint(tint, max(0.0, min(1.0, amount)))
    return colors


def via_pulse(levels, tint, base_brightness):
    """Global VIA update for stock firmware. The caller must not EEPROM-save it."""
    level = max(0.0, min(1.0, float(levels.get("rms") or 0)))
    brightness = max(8, min(255, round(int(base_brightness) * (0.2 + 0.8 * level))))
    highs = 0.0
    bands = list(levels.get("bands") or [])
    if bands:
        highs = sum(bands[-4:]) / min(4, len(bands))
    red, green, blue = hex_to_rgb(tint)
    mix = 0.2 * max(0.0, min(1.0, highs))
    mixed = tuple(round(channel * (1 - mix) + 255 * mix) for channel in (red, green, blue))
    hue, sat, _value = rgb_to_qmk_hsv(*mixed)
    return {"effect": 1, "brightness": brightness, "hue": hue, "sat": sat}


def recorder_command(which=shutil.which):
    if which("pw-record"):
        return [
            "pw-record", "--raw", "--rate", str(RATE), "--channels", "1",
            "--format", "s16", "--target", "@DEFAULT_AUDIO_SINK@.monitor", "-",
        ]
    if which("parecord"):
        return [
            "parecord", "--raw", "--rate=%s" % RATE, "--channels=1",
            "--format=s16le", "--device=@DEFAULT_SINK@.monitor",
        ]
    return None


class MonitorCapture:
    """Read monitor PCM. ``start`` raises OSError when no recorder exists."""

    def __init__(self, popen=subprocess.Popen, which=shutil.which):
        self._popen = popen
        self._which = which
        self.proc = None
        self.rate = RATE
        self.error = ""
        self.failed = False
        self._raw = bytearray()

    def start(self):
        command = recorder_command(self._which)
        if not command:
            raise OSError("pw-record and parecord were not found; music mode needs PipeWire or PulseAudio")
        self.proc = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.set_blocking(self.proc.stdout.fileno(), False)

    def read_samples(self):
        if self.proc is None or self.failed:
            return None
        if self.proc.poll() is not None:
            err = b""
            if self.proc.stderr is not None:
                err = self.proc.stderr.read() or b""
            self.failed = True
            self.error = (err.decode("utf-8", "replace").strip() or "Audio recorder exited")[:300]
            return None
        try:
            chunk = os.read(self.proc.stdout.fileno(), 8192)
        except BlockingIOError:
            chunk = b""
        if chunk:
            self._raw.extend(chunk)
        if len(self._raw) > self.rate * 2:
            self._raw = self._raw[-self.rate * 2:]
        if len(self._raw) < WINDOW * 2:
            return None
        return pcm_s16le(bytes(self._raw[-(WINDOW * 2):]))

    def stop(self):
        proc = self.proc
        self.proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()


class MusicSession:
    def __init__(self, capture=None):
        self.capture = capture
        self.error = ""
        self.running = False
        self.envelope = Envelope()

    def start(self):
        if self.running:
            return
        if self.capture is None or self.capture.failed:
            self.capture = MonitorCapture()
        self.capture.start()
        self.running = True
        self.error = ""

    def poll(self):
        if not self.running or self.capture is None:
            return None
        try:
            samples = self.capture.read_samples()
        except OSError as exc:
            self.error = str(exc)[:300]
            self.running = False
            return None
        if self.capture.failed:
            self.error = self.capture.error
            self.running = False
            return None
        if not samples:
            return None
        return self.envelope.update(analyze(samples, self.capture.rate))

    def stop(self):
        if self.capture is not None:
            self.capture.stop()
        self.running = False
        self.envelope = Envelope()
