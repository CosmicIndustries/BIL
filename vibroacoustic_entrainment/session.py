"""Orchestrates a full session render: audio + haptic + photic, one shared clock.

Everything a playback rig needs is written into ``output_dir``:

* ``audio.wav`` — binaural (stereo) or monaural/isochronic (mono) track, for headphones
  or speakers.
* ``haptic.wav`` — audio-rate tactile-transducer drive signal (present unless
  ``config.haptic_mode`` is ``None``).
* ``haptic_envelope.json`` — coarse PWM envelope for a microcontroller-driven haptic
  motor rig (always written alongside ``haptic.wav``, for rigs that want both).
* ``photic_events.json`` — LED/strobe brightness keyframes (present unless
  ``config.photic_enabled`` is False).
* ``manifest.json`` — stage boundaries, config, sample rates and any safety warnings,
  so a player can line the three tracks up and a human can see what was generated
  and why.

All three modality renderers key off the same ``Protocol.phase_at(t)``, so playing
``audio.wav``, ``haptic.wav`` and stepping through ``photic_events.json`` from a
common ``t = 0`` keeps them phase-locked for the whole session.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os

from . import haptic, oscillators, photic
from .oscillators import DEFAULT_SAMPLE_RATE
from .protocol import Protocol
from .safety import check_haptic_band, check_photic_safety, check_session_duration

AUDIO_MODES = ("binaural", "monaural", "isochronic")
HAPTIC_MODES = ("constant_carrier", "entrainment_locked")


BIT_DEPTHS = (16, 32)


@dataclass
class SessionConfig:
    audio_mode: str = "binaural"
    sample_rate: int = DEFAULT_SAMPLE_RATE
    bit_depth: int = 16
    audio_amplitude: float = 0.5

    haptic_mode: str | None = "entrainment_locked"
    haptic_carrier_hz: float = haptic.DEFAULT_TACTILE_CARRIER_HZ
    haptic_amplitude: float = 0.8
    haptic_control_rate_hz: float = 100.0

    photic_enabled: bool = True
    photic_waveform: str = "sine"
    photic_control_rate_hz: float = photic.DEFAULT_CONTROL_RATE_HZ

    acknowledge_risks: bool = False

    def __post_init__(self) -> None:
        if self.audio_mode not in AUDIO_MODES:
            raise ValueError(f"audio_mode must be one of {AUDIO_MODES}")
        if self.haptic_mode is not None and self.haptic_mode not in HAPTIC_MODES:
            raise ValueError(f"haptic_mode must be one of {HAPTIC_MODES} or None")
        if self.bit_depth not in BIT_DEPTHS:
            raise ValueError(f"bit_depth must be one of {BIT_DEPTHS}")


def collect_safety_warnings(protocol: Protocol, config: SessionConfig) -> list[str]:
    """Run every applicable safety check and return the combined warning list.

    Does not raise; callers that want the hard failure for unacknowledged
    square-wave photic risk should call ``photic.render_photic_events`` (or
    ``safety.check_photic_safety`` directly), which raises
    ``EntrainmentSafetyError`` in that case.
    """
    warnings = list(check_session_duration(protocol))
    if config.haptic_mode is not None:
        warnings += check_haptic_band(config.haptic_carrier_hz)
    if config.photic_enabled:
        try:
            warnings += check_photic_safety(
                protocol, waveform=config.photic_waveform, acknowledge_risks=config.acknowledge_risks
            )
        except Exception as exc:  # surfaced as a warning here; render still raises
            warnings.append(f"BLOCKING: {exc}")
    return warnings


def _resolve_output_dir(output_dir: str) -> str:
    """Validate and resolve the session output directory before any filesystem call.

    Rejects a parent-directory (``..``) segment outright, then resolves symlinks
    and relative components so every later join and the initial ``os.makedirs``
    call all operate on the same, already-validated absolute path — no filesystem
    call in this module ever touches the raw, unvalidated ``output_dir`` argument.
    """
    if os.pardir in os.path.normpath(output_dir).split(os.sep):
        raise ValueError(f"output_dir must not contain {os.pardir!r} segments: {output_dir!r}")
    return os.path.realpath(output_dir)


def _output_path(output_dir: str, filename: str) -> str:
    """Resolve ``filename`` under an already-``_resolve_output_dir``-validated ``output_dir``.

    ``filename`` is always one of this module's own fixed constants (never derived
    from configuration or CLI input), but this still validates the resolved path
    stays within ``output_dir`` as defense in depth against path traversal.
    """
    candidate = os.path.realpath(os.path.join(output_dir, filename))
    if os.path.commonpath([output_dir, candidate]) != output_dir:
        raise ValueError(f"refusing to write outside output_dir: {filename!r}")
    return candidate


def render_session(protocol: Protocol, config: SessionConfig, output_dir: str) -> dict:
    """Render every configured channel into ``output_dir``. Returns the manifest dict."""
    output_dir = _resolve_output_dir(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    warnings = collect_safety_warnings(protocol, config)

    manifest: dict = {
        "protocol": protocol.name,
        "description": protocol.description,
        "carrier_hz": protocol.carrier_hz,
        "total_duration_s": protocol.total_duration,
        "stages": protocol.stage_boundaries,
        "config": asdict(config),
        "safety_warnings": warnings,
        "files": {},
    }

    sample_width = config.bit_depth // 8

    if config.audio_mode == "binaural":
        left, right = oscillators.render_binaural(
            protocol, config.sample_rate, config.audio_amplitude, bit_depth=config.bit_depth,
        )
        audio_path = _output_path(output_dir, "audio.wav")
        oscillators.write_wav_stereo(audio_path, left, right, config.sample_rate, sample_width)
    else:
        renderer = oscillators.render_monaural if config.audio_mode == "monaural" else oscillators.render_isochronic
        mono = renderer(protocol, config.sample_rate, config.audio_amplitude, bit_depth=config.bit_depth)
        audio_path = _output_path(output_dir, "audio.wav")
        oscillators.write_wav_mono(audio_path, mono, config.sample_rate, sample_width)
    manifest["files"]["audio"] = os.path.basename(audio_path)

    if config.haptic_mode is not None:
        haptic_track = haptic.render_haptic_track(
            protocol,
            sample_rate=config.sample_rate,
            mode=config.haptic_mode,
            tactile_carrier_hz=config.haptic_carrier_hz,
            amplitude=config.haptic_amplitude,
        )
        haptic_wav_path = _output_path(output_dir, "haptic.wav")
        oscillators.write_wav_mono(haptic_wav_path, haptic_track, config.sample_rate)
        manifest["files"]["haptic_wav"] = os.path.basename(haptic_wav_path)

        envelope = haptic.render_haptic_envelope_json(
            protocol, control_rate_hz=config.haptic_control_rate_hz, mode=config.haptic_mode
        )
        haptic_json_path = _output_path(output_dir, "haptic_envelope.json")
        with open(haptic_json_path, "w") as f:
            json.dump(envelope, f)
        manifest["files"]["haptic_envelope"] = os.path.basename(haptic_json_path)

    if config.photic_enabled:
        events = photic.render_photic_events(
            protocol,
            control_rate_hz=config.photic_control_rate_hz,
            waveform=config.photic_waveform,
            acknowledge_risks=config.acknowledge_risks,
        )
        photic_path = _output_path(output_dir, "photic_events.json")
        with open(photic_path, "w") as f:
            json.dump(events, f)
        manifest["files"]["photic_events"] = os.path.basename(photic_path)

    manifest_path = _output_path(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


__all__ = ["SessionConfig", "render_session", "collect_safety_warnings", "AUDIO_MODES", "HAPTIC_MODES"]
