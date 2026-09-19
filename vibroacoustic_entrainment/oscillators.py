"""Audio rendering: binaural, monaural and isochronic entrainment tones.

All three modes share one goal — drive the target "entrainment frequency" defined by
a :class:`~vibroacoustic_entrainment.protocol.Protocol` into a Frequency Following
Response — but differ in how the ear/brain gets that frequency:

* **Binaural beat** — two pure tones a few Hz apart, one per ear. The beat frequency
  is a perceptual artifact created in the brainstem (superior olivary complex), not
  physically present in either channel. Requires stereo headphones.
* **Monaural beat** — the same two tones summed acoustically *before* it reaches the
  ear, so the beat is a physically real amplitude-modulated waveform. Works on
  speakers, doesn't require headphones.
* **Isochronic tone** — a single carrier tone pulsed on/off (gated) at the target
  frequency. Comparative EEG work (Siever/Mind Alive) reports isochronic pulsing
  produces a stronger Frequency Following Response than binaural beats at matched
  intensity, at the cost of being a more overtly "pulsing" sound.

The instantaneous target frequency at any moment comes from ``protocol.freq_at(t)``;
the phase used to render each waveform comes from ``protocol.phase_at(t)``, which is
the exact closed-form integral of that frequency schedule — so ramps between stages
never introduce phase discontinuities (audible clicks/pops).
"""

from __future__ import annotations

import array
import math
import wave

from .protocol import Protocol
from .safety import clamp_amplitude

DEFAULT_SAMPLE_RATE = 44100


def _n_samples(duration_s: float, sample_rate: int) -> int:
    return max(1, round(duration_s * sample_rate))


def _to_pcm16(samples: list[float]) -> "array.array[int]":
    out = array.array("h")
    for x in samples:
        x = clamp_amplitude(x)
        out.append(int(x * 32767))
    return out


def render_binaural(
    protocol: Protocol,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = 0.5,
) -> tuple["array.array[int]", "array.array[int]"]:
    """Render a stereo binaural-beat track. Returns (left, right) PCM16 sample arrays."""
    n = _n_samples(protocol.total_duration, sample_rate)
    left = [0.0] * n
    right = [0.0] * n
    carrier_phase_rate = 2 * math.pi * protocol.carrier_hz
    for i in range(n):
        t = i / sample_rate
        carrier_phase = carrier_phase_rate * t
        half_beat_phase = 0.5 * protocol.phase_at(t)
        left[i] = amplitude * math.sin(carrier_phase - half_beat_phase)
        right[i] = amplitude * math.sin(carrier_phase + half_beat_phase)
    return _to_pcm16(left), _to_pcm16(right)


def render_monaural(
    protocol: Protocol,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = 0.5,
) -> "array.array[int]":
    """Render a mono monaural-beat track (physically beating waveform, speaker-safe)."""
    n = _n_samples(protocol.total_duration, sample_rate)
    samples = [0.0] * n
    carrier_phase_rate = 2 * math.pi * protocol.carrier_hz
    for i in range(n):
        t = i / sample_rate
        carrier_phase = carrier_phase_rate * t
        half_beat_phase = 0.5 * protocol.phase_at(t)
        tone_a = math.sin(carrier_phase - half_beat_phase)
        tone_b = math.sin(carrier_phase + half_beat_phase)
        samples[i] = amplitude * 0.5 * (tone_a + tone_b)
    return _to_pcm16(samples)


def _smoothed_gate(cycle_frac: float, duty_cycle: float, edge_frac: float) -> float:
    """Raised-cosine-edged on/off gate value in [0, 1] for a pulse cycle position in [0, 1)."""
    if edge_frac <= 0:
        return 1.0 if cycle_frac < duty_cycle else 0.0
    if cycle_frac < edge_frac:
        return 0.5 - 0.5 * math.cos(math.pi * (cycle_frac / edge_frac))
    if cycle_frac < duty_cycle - edge_frac:
        return 1.0
    if cycle_frac < duty_cycle:
        return 0.5 - 0.5 * math.cos(math.pi * ((duty_cycle - cycle_frac) / edge_frac))
    return 0.0


def render_isochronic(
    protocol: Protocol,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = 0.5,
    duty_cycle: float = 0.5,
    edge_ms: float = 6.0,
) -> "array.array[int]":
    """Render a mono isochronic-tone track: carrier gated on/off at the beat frequency."""
    n = _n_samples(protocol.total_duration, sample_rate)
    samples = [0.0] * n
    carrier_phase_rate = 2 * math.pi * protocol.carrier_hz
    for i in range(n):
        t = i / sample_rate
        carrier = math.sin(carrier_phase_rate * t)
        cycles = protocol.phase_at(t) / (2 * math.pi)
        cycle_frac = cycles - math.floor(cycles)
        freq_now = max(protocol.freq_at(t), 0.01)
        edge_frac = min(0.49, (edge_ms / 1000.0) * freq_now)
        gate = _smoothed_gate(cycle_frac, duty_cycle, edge_frac)
        samples[i] = amplitude * carrier * gate
    return _to_pcm16(samples)


def write_wav_mono(path: str, samples: "array.array[int]", sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())


def write_wav_stereo(
    path: str,
    left: "array.array[int]",
    right: "array.array[int]",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    interleaved = array.array("h")
    interleaved.extend([0] * (2 * len(left)))
    interleaved[0::2] = left
    interleaved[1::2] = right
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(interleaved.tobytes())
