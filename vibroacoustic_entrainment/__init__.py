"""Vibroacoustic + haptovisual brainwave-entrainment session engine.

Generates phase-locked audio (binaural/monaural/isochronic beats), haptic
(vibroacoustic tactile transducer) and photic (strobe/LED) tracks from a shared
frequency-ramp "protocol" — descending through alpha/theta/delta the way the
Monroe Institute's publicly described Gateway Process Focus levels do — for
self-directed relaxation, meditation and altered-state exploration.

Quick start
-----------
>>> from vibroacoustic_entrainment import PROTOCOLS, SessionConfig, render_session
>>> protocol = PROTOCOLS["obe_phase"]()
>>> manifest = render_session(protocol, SessionConfig(), "out/")

Or from the shell::

    python3 -m vibroacoustic_entrainment.cli --protocol obe_phase --out-dir out/

Read ``docs/VIBROACOUSTIC_ENTRAINMENT.md`` before running this against a real
light/haptic rig: it covers the research this is built on, what each protocol
name does and does not claim, and the specific contraindications (photosensitive
epilepsy, cardiac devices, pregnancy, etc.) that ``safety.py`` only partially
encodes as automatic checks.

This project is not affiliated with, endorsed by, or reproducing proprietary
technology from the Monroe Institute, Mind Alive Inc., or Light Attendance GmbH
(Lucia N°03); it implements its own open frequency schedules and signal chains
inspired by the publicly described structure of their work.
"""

from .protocol import (
    Protocol,
    Stage,
    PROTOCOLS,
    gateway_focus10,
    gateway_focus12,
    gateway_focus15,
    gateway_full_progression,
    hyper_cognition_obe_phase_protocol,
    focus21_extended_bridge,
    lucia_hypnagogic,
    vibroacoustic_relaxation,
)
from .audio_output import AudioOutputInfo, detect_audio_output
from .session import SessionConfig, render_session, collect_safety_warnings
from .safety import EntrainmentSafetyError

__all__ = [
    "Protocol",
    "Stage",
    "PROTOCOLS",
    "gateway_focus10",
    "gateway_focus12",
    "gateway_focus15",
    "gateway_full_progression",
    "hyper_cognition_obe_phase_protocol",
    "focus21_extended_bridge",
    "lucia_hypnagogic",
    "vibroacoustic_relaxation",
    "AudioOutputInfo",
    "detect_audio_output",
    "SessionConfig",
    "render_session",
    "collect_safety_warnings",
    "EntrainmentSafetyError",
]
