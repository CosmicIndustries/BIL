"""Photic (visual) entrainment channel: strobe/LED brightness events.

Modeled on "audio-visual entrainment" (AVE) devices (e.g. Mind Alive's David-series)
and hypnagogic light machines (e.g. Lucia N°03), which pair a pulsed light stimulus
with pulsed audio to drive photic driving — an EEG-measurable brainwave response
time-locked to the flicker rate — for a stronger combined effect than either channel
alone. Output is a keyframe list ``[{"t": seconds, "brightness": 0-1}, ...]`` meant to
drive LED goggles or a full-field screen flash, phase-locked to the same beat-phase
used by the audio/haptic renderers via ``protocol.phase_at(t)``.

Waveform choice is a safety-relevant decision, not just an aesthetic one:

* ``"sine"`` (default) — smooth brightness modulation, no harmonic content. Lower
  photosensitive-seizure risk than hard strobing, per epilepsy-safety guidance, while
  still producing a measurable photic-driving response.
* ``"square"`` — hard on/off strobe. Stronger entrainment pull, materially higher
  seizure risk in susceptible individuals. ``safety.check_photic_safety`` raises
  unless the caller explicitly acknowledges the risk for frequencies inside the
  photosensitive caution band.

Always call ``safety.check_photic_safety`` before (or via) rendering; see that
module's docstring for the specific hazard this guards against.
"""

from __future__ import annotations

import math

from .oscillators import _n_samples
from .protocol import Protocol
from .safety import EntrainmentSafetyError, check_photic_safety

DEFAULT_CONTROL_RATE_HZ = 60.0


def render_photic_events(
    protocol: Protocol,
    control_rate_hz: float = DEFAULT_CONTROL_RATE_HZ,
    waveform: str = "sine",
    duty_cycle: float = 0.5,
    max_brightness: float = 1.0,
    min_brightness: float = 0.05,
    acknowledge_risks: bool = False,
) -> list[dict]:
    """Render ``[{"t": seconds, "brightness": 0-1}, ...]`` phase-locked to the protocol.

    Raises :class:`~vibroacoustic_entrainment.safety.EntrainmentSafetyError` for
    unacknowledged square-wave strobing in the photosensitive caution band; see
    ``safety.check_photic_safety``.
    """
    if waveform not in ("sine", "square"):
        raise ValueError("waveform must be 'sine' or 'square'")
    check_photic_safety(protocol, waveform=waveform, acknowledge_risks=acknowledge_risks)

    n = _n_samples(protocol.total_duration, control_rate_hz)
    events = []
    span = max_brightness - min_brightness
    for i in range(n):
        t = i / control_rate_hz
        cycles = protocol.phase_at(t) / (2 * math.pi)
        cycle_frac = cycles - math.floor(cycles)
        if waveform == "sine":
            level = 0.5 - 0.5 * math.cos(2 * math.pi * cycle_frac)
        else:
            level = 1.0 if cycle_frac < duty_cycle else 0.0
        brightness = min_brightness + span * level
        events.append({"t": round(t, 4), "brightness": round(brightness, 4)})
    return events


__all__ = ["DEFAULT_CONTROL_RATE_HZ", "render_photic_events", "EntrainmentSafetyError"]
