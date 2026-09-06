"""Safety checks for the entrainment engine.

None of these checks make the engine "safe" in a medical sense — they encode the
handful of well-documented, specific hazards for this modality combination so the
renderers fail loud instead of silently producing something risky:

* **Photosensitive epilepsy.** Flashing/flickering light in roughly the 3-60 Hz band
  is the internationally recognized caution range for photosensitive seizures (per
  Epilepsy Foundation and ITU/broadcast flash-guideline material); risk peaks around
  15-20 Hz. Square-wave (hard on/off) strobing carries materially more risk than
  sine-wave brightness modulation because it introduces high-frequency harmonics.
* **Vibroacoustic frequency range.** Clinical vibroacoustic therapy literature
  (Skille's Physioacoustic Method onward) works in the 30-120 Hz tactile range, with
  40 Hz cited most often as the well-tolerated default; frequencies outside that
  band are outside what that literature has actually characterized.
* **Session length.** Long unattended low-arousal sessions carry ordinary
  drowsiness/fall-asleep-while-lying-down risk; this is a soft warning, not a hard
  limit.

Nothing here substitutes for a clinician's judgment for anyone with epilepsy,
an implanted cardiac device, a seizure history, migraine with visual aura, is
pregnant, or is otherwise medically vulnerable to rhythmic light/sound/vibration.
"""

from __future__ import annotations

from .protocol import Protocol

PHOTOSENSITIVE_RISK_BAND = (3.0, 60.0)
PHOTOSENSITIVE_PEAK_RISK_BAND = (15.0, 20.0)
VIBROACOUSTIC_RECOMMENDED_BAND = (30.0, 120.0)
DEFAULT_MAX_SESSION_MINUTES = 90.0


class EntrainmentSafetyError(Exception):
    """Raised when a render would produce a known-hazardous stimulus."""


def _protocol_freq_range(protocol: Protocol) -> tuple[float, float]:
    freqs: list[float] = []
    for s in protocol.stages:
        freqs.append(s.freq_start)
        freqs.append(s.freq_end)
    return min(freqs), max(freqs)


def check_photic_safety(
    protocol: Protocol,
    waveform: str = "sine",
    acknowledge_risks: bool = False,
) -> list[str]:
    """Return warnings for a photic render; raise if an unacknowledged hazard exists.

    Square-wave photic stimulation whose frequency range overlaps the photosensitive
    caution band raises :class:`EntrainmentSafetyError` unless the caller passes
    ``acknowledge_risks=True`` (the CLI exposes this as ``--acknowledge-risks``).
    """
    warnings: list[str] = []
    lo, hi = _protocol_freq_range(protocol)
    band_lo, band_hi = PHOTOSENSITIVE_RISK_BAND
    overlaps_band = lo <= band_hi and hi >= band_lo
    peak_lo, peak_hi = PHOTOSENSITIVE_PEAK_RISK_BAND
    overlaps_peak = lo <= peak_hi and hi >= peak_lo

    if overlaps_band:
        msg = (
            f"protocol {protocol.name!r} sweeps {lo:.2f}-{hi:.2f} Hz, which overlaps "
            f"the photosensitive-seizure caution band ({band_lo:.0f}-{band_hi:.0f} Hz)"
        )
        if overlaps_peak:
            msg += f", including the peak-risk sub-band ({peak_lo:.0f}-{peak_hi:.0f} Hz)"
        if waveform == "square":
            if not acknowledge_risks:
                raise EntrainmentSafetyError(
                    msg
                    + ". Square-wave strobing at these frequencies is a recognized "
                    "seizure trigger for photosensitive individuals. Pass "
                    "acknowledge_risks=True only if you have confirmed the user has no "
                    "photosensitive epilepsy, migraine-with-aura, or other flash "
                    "sensitivity, or switch waveform='sine' (no square-wave harmonics)."
                )
            warnings.append("ACKNOWLEDGED RISK: " + msg + " (square wave).")
        else:
            warnings.append(msg + " (sine wave — lower risk, but not risk-free).")
    return warnings


def check_haptic_band(tactile_carrier_hz: float) -> list[str]:
    lo, hi = VIBROACOUSTIC_RECOMMENDED_BAND
    if not (lo <= tactile_carrier_hz <= hi):
        return [
            f"tactile_carrier_hz={tactile_carrier_hz:.1f} Hz is outside the "
            f"vibroacoustic-therapy literature's characterized range ({lo:.0f}-{hi:.0f} Hz); "
            "effects at this frequency are not documented by that body of research."
        ]
    return []


def check_session_duration(protocol: Protocol, max_minutes: float = DEFAULT_MAX_SESSION_MINUTES) -> list[str]:
    minutes = protocol.total_duration / 60.0
    if minutes > max_minutes:
        return [
            f"protocol {protocol.name!r} runs {minutes:.1f} min, longer than the "
            f"{max_minutes:.0f} min default guideline for an unattended low-arousal "
            "session. Consider a spotter/attendant for extended sessions."
        ]
    return []


def clamp_amplitude(x: float) -> float:
    return max(-1.0, min(1.0, x))
