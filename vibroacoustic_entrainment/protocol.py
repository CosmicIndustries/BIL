"""Frequency-schedule protocols for the vibroacoustic / haptovisual entrainment engine.

A ``Protocol`` is an ordered sequence of ``Stage`` objects. Each stage ramps a single
"entrainment frequency" (the target brainwave-following-response rate, in Hz) linearly
from ``freq_start`` to ``freq_end`` over ``duration_s`` seconds. That single frequency
schedule is the master clock shared by the audio (binaural/isochronic), haptic
(vibroacoustic transducer) and photic (strobe/LED) renderers, so all three modalities
stay phase-locked to the same descent through brainwave bands.

Research grounding
-------------------
The Monroe Institute's "Gateway Process" (the Hemi-Sync exercise sequence) is publicly
described as walking a listener down through a series of named "Focus levels" by
sweeping a binaural beat frequency from alpha into theta/delta:

* Focus 10 ("Mind Awake / Body Asleep") — alpha ~10 Hz descending toward ~7 Hz.
* Focus 12 ("Expanded Awareness") — continues the descent into theta, ~7 -> 4 Hz.
* Focus 15 ("No Time") — theta/delta border, ~4 -> 2 Hz.
* Focus 21 ("The Bridge") — described qualitatively in Monroe's own writing and the
  declassified 1983 CIA "Analysis and Assessment of Gateway Process" report as a
  further, less time-bound state; no public source gives a single canonical
  frequency for it.

The Monroe Institute's exact Hemi-Sync signal-processing chain is proprietary. The
stage frequencies below are this project's own interpretation of the *publicly
described* structure of the Focus levels, built for this open engine — they are not a
reproduction of Monroe Institute's trade-secret audio processing, and are not
officially affiliated with or endorsed by the Monroe Institute.

Out-of-body-experience ("phase") induction is likewise not settled neuroscience: it
draws on practitioner literature (Robert Monroe's *Journeys Out of the Body*, Robert
Bruce's *Astral Dynamics* "vibrational stage") describing a prolonged low-theta
plateau paired with a strong, rhythmic full-body sensory pulse as the reported
trigger for the "vibrations"/"rollout" experience. Treat protocol names like
``hyper_cognition_obe_phase_protocol`` as an engineering label for that plateau shape,
not a claim that the state it targets is verified to occur or to be beneficial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class Stage:
    """One linear frequency ramp segment of a protocol.

    ``freq_start``/``freq_end`` are the entrainment (beat) frequency in Hz at the
    start and end of the stage; a flat stage simply repeats the same value.
    """

    name: str
    duration_s: float
    freq_start: float
    freq_end: float
    note: str = ""

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError(f"stage {self.name!r} must have duration_s > 0")
        if self.freq_start <= 0 or self.freq_end <= 0:
            raise ValueError(f"stage {self.name!r} frequencies must be > 0 Hz")

    def freq_at(self, t: float) -> float:
        """Instantaneous frequency at offset ``t`` (seconds) into this stage."""
        t = max(0.0, min(t, self.duration_s))
        rate = (self.freq_end - self.freq_start) / self.duration_s
        return self.freq_start + rate * t

    def phase_at(self, t: float) -> float:
        """Continuous phase (radians) accumulated from stage-start to offset ``t``.

        Closed-form integral of 2*pi*f(tau) d(tau) for a linearly ramping f, so the
        phase is exact (no per-sample accumulation error / no ramp-induced clicks).
        """
        t = max(0.0, min(t, self.duration_s))
        rate = (self.freq_end - self.freq_start) / self.duration_s
        return 2 * math.pi * (self.freq_start * t + 0.5 * rate * t * t)


@dataclass(frozen=True)
class Protocol:
    """An ordered sequence of :class:`Stage` objects sharing one carrier frequency."""

    name: str
    stages: tuple[Stage, ...]
    carrier_hz: float = 200.0
    description: str = ""

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("protocol must have at least one stage")
        if self.carrier_hz <= 0:
            raise ValueError("carrier_hz must be > 0")

    @property
    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.stages)

    @property
    def stage_boundaries(self) -> list[dict]:
        """List of ``{name, start_s, end_s, freq_start, freq_end, note}`` per stage."""
        boundaries = []
        t = 0.0
        for s in self.stages:
            boundaries.append(
                {
                    "name": s.name,
                    "start_s": t,
                    "end_s": t + s.duration_s,
                    "freq_start": s.freq_start,
                    "freq_end": s.freq_end,
                    "note": s.note,
                }
            )
            t += s.duration_s
        return boundaries

    def _locate(self, t: float) -> tuple[Stage, float]:
        """Return (stage, offset_into_stage) for global time ``t``."""
        t = max(0.0, min(t, self.total_duration))
        acc = 0.0
        for s in self.stages:
            if t <= acc + s.duration_s or s is self.stages[-1]:
                return s, t - acc
            acc += s.duration_s
        return self.stages[-1], self.stages[-1].duration_s

    def freq_at(self, t: float) -> float:
        """Instantaneous entrainment frequency (Hz) at global time ``t``."""
        stage, offset = self._locate(t)
        return stage.freq_at(offset)

    def phase_at(self, t: float) -> float:
        """Continuous, click-free phase (radians) of the beat oscillator at time ``t``.

        Phase is carried across stage boundaries so the whole protocol behaves as one
        uninterrupted frequency sweep rather than a series of resets.
        """
        t = max(0.0, min(t, self.total_duration))
        acc_t = 0.0
        acc_phase = 0.0
        for s in self.stages:
            if t <= acc_t + s.duration_s:
                return acc_phase + s.phase_at(t - acc_t)
            acc_phase += s.phase_at(s.duration_s)
            acc_t += s.duration_s
        return acc_phase


def gateway_focus10(duration_s: float = 720.0, carrier_hz: float = 200.0) -> Protocol:
    """Alpha -> low-alpha/theta border. "Mind Awake, Body Asleep." """
    return Protocol(
        name="gateway_focus10",
        carrier_hz=carrier_hz,
        description="Monroe-style Focus 10: relaxed alertness, alpha descending toward theta.",
        stages=(
            Stage("focus10_settle", duration_s * 0.25, 10.0, 10.0, "Alpha settle / body relaxation."),
            Stage("focus10_descend", duration_s * 0.75, 10.0, 7.0, "Alpha -> theta border descent."),
        ),
    )


def gateway_focus12(duration_s: float = 600.0, carrier_hz: float = 200.0) -> Protocol:
    """Continues the descent into theta. "Expanded Awareness."""
    return Protocol(
        name="gateway_focus12",
        carrier_hz=carrier_hz,
        description="Monroe-style Focus 12: theta-dominant expanded awareness.",
        stages=(
            Stage("focus12_bridge", duration_s * 0.2, 7.0, 6.0, "Bridge in from Focus 10."),
            Stage("focus12_theta", duration_s * 0.8, 6.0, 4.0, "Settle into mid/low theta."),
        ),
    )


def gateway_focus15(duration_s: float = 600.0, carrier_hz: float = 200.0) -> Protocol:
    """Theta/delta border. "No Time."""
    return Protocol(
        name="gateway_focus15",
        carrier_hz=carrier_hz,
        description="Monroe-style Focus 15: theta/delta border, minimal cortical arousal.",
        stages=(
            Stage("focus15_bridge", duration_s * 0.25, 4.0, 3.0, "Bridge in from Focus 12."),
            Stage("focus15_delta_theta", duration_s * 0.75, 3.0, 2.0, "Theta/delta border plateau."),
        ),
    )


def gateway_full_progression(carrier_hz: float = 200.0) -> Protocol:
    """Focus 10 -> 12 -> 15 chained into a single continuous-phase protocol."""
    f10 = gateway_focus10(carrier_hz=carrier_hz)
    f12 = gateway_focus12(carrier_hz=carrier_hz)
    f15 = gateway_focus15(carrier_hz=carrier_hz)
    return Protocol(
        name="gateway_full_progression",
        carrier_hz=carrier_hz,
        description="Chained Focus 10 -> 12 -> 15 descent.",
        stages=f10.stages + f12.stages + f15.stages,
    )


def hyper_cognition_obe_phase_protocol(carrier_hz: float = 200.0) -> Protocol:
    """Descent through Focus 10/12/15 into an extended low-theta "phase" plateau.

    The final stage is a long, flat ~4 Hz theta hold with no further frequency
    ramping — modeling the "hold the state, don't fall asleep" instruction common to
    OBE-induction literature (Monroe, Bruce) during the reported vibrational/rollout
    stage. Pair it with ``haptic.render_haptic_track(mode="entrainment_locked")`` and
    ``photic.render_photic_events(...)`` so all three channels pulse together at the
    plateau frequency — the combined full-body pulse is the mechanism this protocol
    is actually testing, not the frequency number in isolation.

    This is a self-exploration protocol, not a medical or clinical one. See
    ``docs/VIBROACOUSTIC_ENTRAINMENT.md`` for contraindications before use.
    """
    f10 = gateway_focus10(duration_s=600.0, carrier_hz=carrier_hz)
    f12 = gateway_focus12(duration_s=480.0, carrier_hz=carrier_hz)
    bridge = Stage("phase_bridge", 180.0, 4.0, 4.0, "Bridge from Focus 12 into the plateau.")
    plateau = Stage(
        "phase_plateau",
        900.0,
        4.0,
        4.0,
        "Extended low-theta hold ('stay in the state') — the target phase window.",
    )
    return Protocol(
        name="hyper_cognition_obe_phase_protocol",
        carrier_hz=carrier_hz,
        description=(
            "Focus 10 -> 12 -> extended 4 Hz theta plateau, modeled on OBE-induction "
            "literature's 'hold the vibrational stage' instruction. Experiential target, "
            "not a validated neuroscience protocol."
        ),
        stages=f10.stages + f12.stages + (bridge, plateau),
    )


PROTOCOLS = {
    "focus10": gateway_focus10,
    "focus12": gateway_focus12,
    "focus15": gateway_focus15,
    "gateway": gateway_full_progression,
    "obe_phase": hyper_cognition_obe_phase_protocol,
}
