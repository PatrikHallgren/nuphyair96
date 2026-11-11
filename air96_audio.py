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


def _hann(samples):
    """A rectangular window leaks one tone across the whole keyboard.

    That leakage is a bright-left, dark-right ramp. Auto-gain then pins the
    bright end at full scale, so the ramp looks the same for hiss and for music.
    """
    count = len(samples)
    if count < 2:
        return list(samples)
    scale = 2 * math.pi / (count - 1)
    return [sample * (0.5 - 0.5 * math.cos(scale * index)) for index, sample in enumerate(samples)]


def analyze(samples, rate=RATE, bands=BANDS):
    window = list(samples[-WINDOW:])
    level = min(1.0, rms(window))
    shaped = _hann(window)
    magnitudes = _fft(shaped) if shaped else []
    size = len(magnitudes) * 2 or 1
    edges = _band_edges(rate, bands)
    values = []
    for index in range(bands):
        start = edges[index]
        end = edges[index + 1]
        # Peak bin, not the mean. Log bands get wider toward the treble, so an
        # average shrinks every high band and paints a left-to-right ramp.
        peak = 0.0
        bins = 0
        for bin_index, magnitude in enumerate(magnitudes):
            frequency = bin_index * rate / size
            if frequency < start or frequency >= end:
                continue
            if magnitude > peak:
                peak = magnitude
            bins += 1
        values.append(peak if bins else 0.0)
    bass = sum(values[:3]) / 3 if values else 0.0
    highs = sum(values[-3:]) / 3 if values else 0.0
    return {"rms": level, "bands": values, "bass": bass, "highs": highs}


class Envelope:
    """Fast attack, slow decay, a noise gate, and per-band automatic gain.

    One global gain keeps a bass-heavy spectrum bass-heavy: the left columns
    stay bright and the right columns never reach full scale. Each band is
    scaled to its own recent peak, then a floor drops bands that are just
    leakage or silence. Loudness is still global, so a quiet room stays dark.

    nuphy-rgb-music decays each frame (about 0.97 at 30 fps) so a beat has a
    tail. This HID path cannot repaint every LED that often, so the tail is
    a bit faster and the picture only sends the LEDs that moved.
    """

    def __init__(self, attack=0.65, decay=0.88, open_at=0.018, close_at=0.010):
        self.attack = attack
        self.decay = decay
        self.open_at = open_at
        self.close_at = close_at
        self.relative_floor = 0.04
        self.absolute_floor = 1e-5
        # Start at the floor. A 0.05 seed made a real but quiet band look dim
        # until the seed decayed, so treble columns never caught the bass.
        self.peaks = [self.absolute_floor] * BANDS
        self.loud = 0.0
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
        global_peak = max(incoming) if incoming else 0.0
        floor = max(self.absolute_floor, global_peak * self.relative_floor)
        target = []
        for index, value in enumerate(incoming):
            if not self.open or value < floor:
                self.peaks[index] = max(self.absolute_floor, self.peaks[index] * 0.995)
                target.append(0.0)
                continue
            peak = self.peaks[index]
            if value > peak:
                peak = peak * 0.4 + value * 0.6
            else:
                peak = peak * 0.995 + value * 0.005
            peak = max(peak, self.absolute_floor)
            self.peaks[index] = peak
            target.append(min(1.0, value / peak))
        rising = (max(target) if target else 0.0) >= self.level
        keep = (1.0 - self.attack) if rising else self.decay
        take = 1.0 - keep
        blended = [old * keep + new * take for old, new in zip(self.bands, target)]
        self.bands = blended
        self.level = max(blended) if blended else 0.0
        # Shape can stay normalized. Brightness has to follow the actual level
        # or a beat cannot get brighter than the hiss it replaced.
        if not self.open:
            loud_target = 0.0
        else:
            loud_target = min(1.0, rms_level / 0.12)
        if loud_target >= self.loud:
            self.loud = self.loud * 0.15 + loud_target * 0.85
        else:
            self.loud = self.loud * self.decay + loud_target * (1.0 - self.decay)
        shown = [value * self.loud for value in blended]
        silent = (not self.open) and max(shown, default=0.0) < 0.04
        return {
            "rms": 0.0 if silent else min(1.0, max(self.loud, rms_level if self.open else 0.0)),
            "bands": shown,
            "bass": sum(shown[:3]) / 3,
            "highs": sum(shown[-3:]) / 3,
            "loudness": self.loud,
            "silent": silent,
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
    span = max(key["x"] + key["w"] for key in keys) or 1
    last = len(bands) - 1
    for key in keys:
        center = key["x"] + key["w"] / 2
        # The rightmost center can equal the span. Keep it on the last band.
        index = min(last, int(center / span * len(bands)))
        if index < 0:
            index = 0
        amount = bands[index]
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


def pipewire_monitor_target(run=subprocess.run):
    """Node name of the default speakers' monitor, for pw-record --target.

    pw-record does not treat ``@DEFAULT_AUDIO_SINK@.monitor`` as a special
    name. Its default capture target is the microphone. pactl's sink name
    plus ``.monitor`` is the mix actually playing through that sink.
    """
    try:
        result = run(["pactl", "get-default-sink"], capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    name = (result.stdout or b"").decode("utf-8", "replace").strip()
    if not name or any(character.isspace() for character in name) or name.startswith("@"):
        return None
    return name + ".monitor"


def recorder_command(which=shutil.which, resolve_monitor=pipewire_monitor_target):
    """Capture the default speakers, not the microphone.

    ``parecord --device=@DEFAULT_MONITOR@`` is pipewire-pulse's name for the
    monitor of the default sink. It follows headphones and speakers. pw-record
    is only used when that command is missing, and only with a resolved
    monitor node. ``@DEFAULT_AUDIO_SINK@.monitor`` is not a pw-record target;
    leaving the target off records the microphone, which does not move when
    music plays through the speakers or headphones.
    """
    if which("parecord"):
        return [
            "parecord", "--raw", "--rate=%s" % RATE, "--channels=1",
            "--format=s16le", "--device=@DEFAULT_MONITOR@",
        ]
    if which("pw-record"):
        target = resolve_monitor() if resolve_monitor else None
        if not target:
            return None
        return [
            "pw-record", "--raw", "--rate", str(RATE), "--channels", "1",
            "--format", "s16", "--target", target, "-",
        ]
    return None


class MonitorCapture:
    """Read monitor PCM. ``start`` raises OSError when no recorder exists."""

    def __init__(self, popen=subprocess.Popen, which=shutil.which):
        self._popen = popen
        self._which = which
        self.proc = None
        self.rate = RATE
        self.command = []
        self.error = ""
        self.failed = False
        self.stalled = False
        self.bytes_total = 0
        self._stalls = 0
        self._raw = bytearray()

    def start(self):
        command = recorder_command(self._which)
        if not command:
            raise OSError(
                "Could not open the speaker monitor. parecord is missing, and pw-record "
                "needs the default sink from pactl. Refusing to record the microphone."
            )
        self.command = list(command)
        self.proc = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.set_blocking(self.proc.stdout.fileno(), False)
        if self.proc.stderr is not None:
            os.set_blocking(self.proc.stderr.fileno(), False)

    def _drain(self, stream):
        if stream is None:
            return b""
        chunks = []
        while True:
            try:
                chunk = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def read_samples(self):
        if self.proc is None or self.failed:
            return None
        note = self._drain(self.proc.stderr).decode("utf-8", "replace").strip()
        if self.proc.poll() is not None:
            self.failed = True
            self.stalled = True
            self.error = (note or self.error or "Audio recorder exited")[:300]
            return None
        chunk = self._drain(self.proc.stdout)
        if chunk:
            self.bytes_total += len(chunk)
            self._raw.extend(chunk)
            self._stalls = 0
            self.stalled = False
            # A live monitor is not an error. A recorder banner on stderr must
            # not stick, or status reports a failure while audio is flowing.
            self.error = ""
        else:
            self._stalls += 1
            # About half a second at the worker's poll rate. The last window
            # is then a frozen spectrum, which is what a keepalive would hold
            # on the keys. Drop it so the lights can decay.
            self.stalled = self._stalls >= 8
        if len(self._raw) > self.rate * 2:
            self._raw = self._raw[-self.rate * 2:]
        if self.stalled or len(self._raw) < WINDOW * 2:
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
        self.last_levels = None

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
            self.last_levels = self.envelope.update({"rms": 0.0, "bands": [0.0] * BANDS})
            return self.last_levels
        if self.capture.stalled:
            self.error = self.capture.error or (
                "The recorder stopped sending samples. The last window is not live audio, so the lights are fading."
            )
            self.last_levels = self.envelope.update({"rms": 0.0, "bands": [0.0] * BANDS})
            return self.last_levels
        if not samples:
            self.last_levels = None
            return None
        if not self.capture.error:
            self.error = ""
        self.last_levels = self.envelope.update(analyze(samples, self.capture.rate))
        return self.last_levels

    def stop(self):
        if self.capture is not None:
            self.capture.stop()
        self.running = False
        self.envelope = Envelope()
