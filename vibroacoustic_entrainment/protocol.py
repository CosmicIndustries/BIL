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

Three further protocols extend this beyond the core Gateway descent:

* ``focus21_extended_bridge`` — Monroe's own material and the declassified CIA
  Gateway report describe Focus 21 only qualitatively ("The Bridge", a state
  further removed from ordinary consciousness with no time-bound frequency
  given). This protocol is this project's own speculative extrapolation past
  Focus 15 into a brief deep-delta trough and back — clearly a guess beyond any
  public source, not a reconstruction of anything Monroe specified.
* ``lucia_hypnagogic`` — modeled on the *publicly described operating pattern*
  of the Lucia N°03 stroboscope (Proeckl & Winkler): a light-forward session
  that steps through a handful of fixed frequencies rather than one continuous
  descent, commonly reported in coverage of the device as roughly 3 Hz (delta),
  6 Hz (theta), 10 Hz (alpha) and higher bands, holding briefly at each before
  moving on. Meant to be run with a photic-forward ``SessionConfig``
  (``photic_enabled=True``, audio kept low/off) — this project has no
  affiliation with Light Attendance GmbH and does not reproduce their device's
  actual signal chain.
* ``vibroacoustic_relaxation`` — a non-altered-state, therapy-style session
  grounded in Olav Skille's Physioacoustic Method and the applications
  reviewed in Boyd-Brewer & Punzi's 2005 vibroacoustic-therapy literature
  review (muscle relaxation, pain and anxiety reduction): a long, flat alpha
  hold rather than a theta/delta descent, meant to be run haptic-forward
  (higher ``haptic_amplitude``) with the audio/photic channels as secondary
  accompaniment, not the point of the session.
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


def focus21_extended_bridge(carrier_hz: float = 200.0) -> Protocol:
    """Speculative extension past Focus 15 into a brief deep-delta trough and back.

    Monroe's own descriptions of Focus 21 ("The Bridge") give no canonical
    frequency, so this is an engineering guess at what "further removed, still
    reversible" might look like as a schedule shape: dip below the Focus 15
    floor into slow delta, hold briefly, then bridge back up toward alpha
    rather than ending on a low plateau (unlike ``obe_phase``, which is built
    to hold the state). Chains after the full Focus 10/12/15 descent.
    """
    gateway = gateway_full_progression(carrier_hz=carrier_hz)
    trough = Stage("focus21_trough", 300.0, 2.0, 1.0, "Speculative deep-delta dip past the Focus 15 floor.")
    hold = Stage("focus21_hold", 240.0, 1.0, 1.0, "Brief hold at the trough.")
    bridge_back = Stage("focus21_bridge_back", 360.0, 1.0, 8.0, "Bridge back up toward alpha.")
    return Protocol(
        name="focus21_extended_bridge",
        carrier_hz=carrier_hz,
        description=(
            "Speculative extension past Focus 15: a brief deep-delta trough and a "
            "bridge back to alpha. Not sourced from any public Focus 21 frequency "
            "(none is given) — this project's own guess at the schedule shape."
        ),
        stages=gateway.stages + (trough, hold, bridge_back),
    )


def lucia_hypnagogic(carrier_hz: float = 200.0) -> Protocol:
    """Stepped multi-band schedule modeled on Lucia N°03's publicly described presets.

    Rather than one continuous descent, steps through delta, theta, alpha and a
    higher band with a short ramp and hold at each — meant to be paired with a
    photic-forward ``SessionConfig`` (light channel is the point; audio/haptic
    are secondary). Not a reproduction of the Lucia N°03 device's actual signal
    chain, which is proprietary.
    """
    return Protocol(
        name="lucia_hypnagogic",
        carrier_hz=carrier_hz,
        description=(
            "Photic-forward stepped session modeled on Lucia N°03's publicly "
            "reported frequency presets (delta -> theta -> alpha -> higher band), "
            "for hypnagogic-imagery exploration under closed eyelids."
        ),
        stages=(
            Stage("lucia_settle", 60.0, 10.0, 10.0, "Eyes closed, settle with the light on."),
            Stage("lucia_ramp_delta", 60.0, 10.0, 3.0, "Ramp down toward the delta preset."),
            Stage("lucia_delta_hold", 180.0, 3.0, 3.0, "Hold at ~3 Hz (delta preset)."),
            Stage("lucia_ramp_theta", 45.0, 3.0, 6.0, "Ramp up toward the theta preset."),
            Stage("lucia_theta_hold", 180.0, 6.0, 6.0, "Hold at ~6 Hz (theta preset)."),
            Stage("lucia_ramp_alpha", 45.0, 6.0, 10.0, "Ramp up toward the alpha preset."),
            Stage("lucia_alpha_hold", 180.0, 10.0, 10.0, "Hold at ~10 Hz (alpha preset)."),
            Stage("lucia_ramp_high", 45.0, 10.0, 18.0, "Ramp up into a higher, more alerting band."),
            Stage("lucia_high_hold", 120.0, 18.0, 18.0, "Hold at ~18 Hz before closing out."),
            Stage("lucia_return", 90.0, 18.0, 10.0, "Return to alpha to close the session."),
        ),
    )


def vibroacoustic_relaxation(carrier_hz: float = 100.0) -> Protocol:
    """Long, flat alpha hold for haptic-forward physical relaxation (Skille-style).

    Unlike the Gateway/OBE protocols, this is not trying to descend into
    theta/delta or induce an altered state — it targets the same relaxed-alpha
    band the whole session through, so the vibroacoustic tactile channel (run
    with a higher ``haptic_amplitude``) is doing the work described in Skille's
    Physioacoustic Method and the applications literature (muscle relaxation,
    pain and anxiety reduction), with audio/photic as light accompaniment.
    """
    return Protocol(
        name="vibroacoustic_relaxation",
        carrier_hz=carrier_hz,
        description=(
            "Haptic-forward flat-alpha relaxation session (Skille Physioacoustic "
            "Method style) — run with a higher haptic_amplitude; not a theta/delta "
            "descent and not aimed at an altered state."
        ),
        stages=(
            Stage("relax_settle", 120.0, 10.0, 10.0, "Settle in; let the tactile pulse take over."),
            Stage("relax_hold", 1080.0, 10.0, 10.0, "Extended relaxed-alpha hold."),
            Stage("relax_ease_out", 120.0, 10.0, 10.0, "Ease out; stay flat, just wind down attention."),
        ),
    )


PROTOCOLS = {
    "focus10": gateway_focus10,
    "focus12": gateway_focus12,
    "focus15": gateway_focus15,
    "gateway": gateway_full_progression,
    "obe_phase": hyper_cognition_obe_phase_protocol,
    "focus21_bridge": focus21_extended_bridge,
    "lucia_hypnagogic": lucia_hypnagogic,
    "vibroacoustic_relaxation": vibroacoustic_relaxation,
}
