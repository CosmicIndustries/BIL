"""Detect system audio output configuration via PulseAudio/PipeWire.

Probes the default sink using ``pactl`` to discover sample rate, sample format,
channel count, volume, and mute state.  Falls back gracefully when ``pactl`` is
unavailable or the output cannot be parsed — every field in the returned
:class:`AudioOutputInfo` defaults to ``None`` and callers decide what to do with
missing values.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass


PACTL_FORMAT_BITS = {
    "u8": 8,
    "s16le": 16, "s16be": 16,
    "s24le": 24, "s24be": 24, "s24-32le": 24, "s24-32be": 24,
    "s32le": 32, "s32be": 32,
    "float32le": 32, "float32be": 32,
}


@dataclass
class AudioOutputInfo:
    """Snapshot of the system's default audio sink configuration."""
    sink_name: str | None = None
    sample_rate: int | None = None
    sample_format: str | None = None
    bit_depth: int | None = None
    channels: int | None = None
    volume_pct: int | None = None
    muted: bool | None = None
    server: str | None = None

    @property
    def matched_sample_rate(self) -> int | None:
        return self.sample_rate

    @property
    def matched_bit_depth(self) -> int | None:
        if self.bit_depth and self.bit_depth in (16, 32):
            return self.bit_depth
        if self.bit_depth and self.bit_depth > 16:
            return 32
        return 16


def _run_pactl(*args: str) -> str | None:
    if not shutil.which("pactl"):
        return None
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _parse_sink_name(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"Default Sink:\s*(.+)", text)
    return m.group(1).strip() if m else None


def _parse_sinks_short(text: str | None, sink_name: str | None) -> dict:
    """Parse ``pactl list sinks short`` for format/rate/channels of the target sink."""
    if not text or not sink_name:
        return {}
    for line in text.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 4 and parts[1].strip() == sink_name:
            spec = parts[3].strip()
            info: dict = {}
            m = re.match(r"([a-z0-9_-]+)\s+(\d+)ch\s+(\d+)Hz", spec, re.I)
            if m:
                info["sample_format"] = m.group(1).lower()
                info["channels"] = int(m.group(2))
                info["sample_rate"] = int(m.group(3))
                info["bit_depth"] = PACTL_FORMAT_BITS.get(info["sample_format"])
            return info
    return {}


def _parse_volume(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)%", text)
    return int(m.group(1)) if m else None


def _parse_mute(text: str | None) -> bool | None:
    if not text:
        return None
    m = re.search(r"Mute:\s*(yes|no)", text, re.I)
    if m:
        return m.group(1).lower() == "yes"
    return None


def _parse_server(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"Server Name:\s*(.+)", text)
    return m.group(1).strip() if m else None


def detect_audio_output() -> AudioOutputInfo:
    """Probe the system's default audio sink and return its configuration.

    Returns an :class:`AudioOutputInfo` with as many fields filled in as
    ``pactl`` can provide.  Every field defaults to ``None`` when detection
    fails, so callers can fall back to their own defaults.
    """
    info_text = _run_pactl("info")
    sink_name = _parse_sink_name(info_text)

    sinks_text = _run_pactl("list", "sinks", "short")
    sink_props = _parse_sinks_short(sinks_text, sink_name)

    vol_text = _run_pactl("get-sink-volume", "@DEFAULT_SINK@")
    mute_text = _run_pactl("get-sink-mute", "@DEFAULT_SINK@")

    return AudioOutputInfo(
        sink_name=sink_name,
        sample_rate=sink_props.get("sample_rate"),
        sample_format=sink_props.get("sample_format"),
        bit_depth=sink_props.get("bit_depth"),
        channels=sink_props.get("channels"),
        volume_pct=_parse_volume(vol_text),
        muted=_parse_mute(mute_text),
        server=_parse_server(info_text),
    )


__all__ = ["AudioOutputInfo", "detect_audio_output", "PACTL_FORMAT_BITS"]
