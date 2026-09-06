"""Haptic / vibroacoustic tactile channel.

Two output shapes are provided, matching two different real rigs:

* :func:`render_haptic_track` — an audio-rate PCM signal meant to drive a bass-shaker
  or vibroacoustic transducer (a "vibroacoustic chair/mat", the same class of
  hardware Monroe's CHEC unit and clinical VAT rigs use) through a normal amplifier,
  exactly like a second audio channel.
* :func:`render_haptic_envelope_json` — a coarse control-rate envelope (default
  100 Hz) meant for a microcontroller driving small ERM/LRA vibration motors via
  PWM, where "duty" 0-255 is the motor drive strength at that instant.

Two drive modes:

* ``"constant_carrier"`` — a fixed tactile-range carrier (default 40 Hz, the
  frequency clinical vibroacoustic-therapy literature cites most often as a
  well-tolerated default within the 30-120 Hz range that literature characterizes)
  held at a steady low-level hum for the whole session — the "vibroacoustic bed"
  component.
* ``"entrainment_locked"`` — the same tactile carrier, but amplitude-gated on/off at
  the protocol's beat frequency (using the identical phase used by the audio and
  photic renderers), so the body feels a rhythmic pulse phase-locked to the
  audio/light — this is the full-body-pulse component OBE-induction literature
  describes pairing with the low-theta plateau.
"""

from __future__ import annotations

import array
import math

from .oscillators import DEFAULT_SAMPLE_RATE, _n_samples, _smoothed_gate, _to_pcm16
from .protocol import Protocol
from .safety import check_haptic_band

DEFAULT_TACTILE_CARRIER_HZ = 40.0


def render_haptic_track(
    protocol: Protocol,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    mode: str = "entrainment_locked",
    tactile_carrier_hz: float = DEFAULT_TACTILE_CARRIER_HZ,
    amplitude: float = 0.8,
    duty_cycle: float = 0.5,
    edge_ms: float = 15.0,
) -> "array.array[int]":
    """Render a mono PCM16 tactile-transducer drive signal.

    Raises no exception itself; callers should surface
    ``safety.check_haptic_band(tactile_carrier_hz)`` warnings before rendering.
    """
    if mode not in ("constant_carrier", "entrainment_locked"):
        raise ValueError("mode must be 'constant_carrier' or 'entrainment_locked'")
    n = _n_samples(protocol.total_duration, sample_rate)
    samples = [0.0] * n
    carrier_phase_rate = 2 * math.pi * tactile_carrier_hz
    for i in range(n):
        t = i / sample_rate
        carrier = math.sin(carrier_phase_rate * t)
        if mode == "constant_carrier":
            samples[i] = amplitude * carrier
        else:
            cycles = protocol.phase_at(t) / (2 * math.pi)
            cycle_frac = cycles - math.floor(cycles)
            freq_now = max(protocol.freq_at(t), 0.01)
            edge_frac = min(0.49, (edge_ms / 1000.0) * freq_now)
            gate = _smoothed_gate(cycle_frac, duty_cycle, edge_frac)
            samples[i] = amplitude * carrier * gate
    return _to_pcm16(samples)


def render_haptic_envelope_json(
    protocol: Protocol,
    control_rate_hz: float = 100.0,
    mode: str = "entrainment_locked",
    duty_cycle: float = 0.5,
    edge_ms: float = 15.0,
    max_duty: int = 255,
) -> list[dict]:
    """Render a coarse ``[{"t": seconds, "duty": 0-255}, ...]`` envelope for a PWM
    haptic-motor controller (no audio-rate carrier needed at this control rate)."""
    if mode not in ("constant_carrier", "entrainment_locked"):
        raise ValueError("mode must be 'constant_carrier' or 'entrainment_locked'")
    n = _n_samples(protocol.total_duration, control_rate_hz)
    events = []
    for i in range(n):
        t = i / control_rate_hz
        if mode == "constant_carrier":
            duty = max_duty
        else:
            cycles = protocol.phase_at(t) / (2 * math.pi)
            cycle_frac = cycles - math.floor(cycles)
            freq_now = max(protocol.freq_at(t), 0.01)
            edge_frac = min(0.49, (edge_ms / 1000.0) * freq_now)
            gate = _smoothed_gate(cycle_frac, duty_cycle, edge_frac)
            duty = round(gate * max_duty)
        events.append({"t": round(t, 4), "duty": duty})
    return events


__all__ = [
    "DEFAULT_TACTILE_CARRIER_HZ",
    "render_haptic_track",
    "render_haptic_envelope_json",
    "check_haptic_band",
]
