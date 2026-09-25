"""Command-line entry point.

    python3 -m vibroacoustic_entrainment.cli --protocol obe_phase --out-dir out/

See ``docs/VIBROACOUSTIC_ENTRAINMENT.md`` for what each protocol/mode means and the
safety disclaimers that apply before you point this at a real light/haptic rig.
"""

from __future__ import annotations

import argparse
import sys

from .audio_output import AudioOutputInfo, detect_audio_output
from .protocol import PROTOCOLS
from .safety import EntrainmentSafetyError
from .session import SessionConfig, render_session


def _print_audio_info(info: AudioOutputInfo) -> None:
    print("System audio output:")
    print(f"  Sink:        {info.sink_name or '(unknown)'}")
    print(f"  Server:      {info.server or '(unknown)'}")
    print(f"  Sample rate: {info.sample_rate or '(unknown)'} Hz")
    print(f"  Format:      {info.sample_format or '(unknown)'} ({info.bit_depth or '?'}-bit)")
    print(f"  Channels:    {info.channels or '(unknown)'}")
    print(f"  Volume:      {info.volume_pct or '?'}%")
    print(f"  Muted:       {info.muted if info.muted is not None else '(unknown)'}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render a vibroacoustic/haptovisual entrainment session.")
    p.add_argument("--protocol", choices=sorted(PROTOCOLS), default="obe_phase")
    p.add_argument("--carrier-hz", type=float, default=200.0, help="Audio carrier tone, Hz.")
    p.add_argument("--out-dir", default="entrainment_session_output")

    p.add_argument("--audio-mode", choices=("binaural", "monaural", "isochronic"), default="binaural")
    p.add_argument("--audio-amplitude", type=float, default=0.5)
    p.add_argument("--sample-rate", type=int, default=44100)
    p.add_argument("--bit-depth", type=int, choices=(16, 32), default=16,
                   help="WAV bit depth — 16 (default) or 32. Use 32 for systems running S32LE.")

    p.add_argument("--match-system", action="store_true",
                   help="Auto-detect PulseAudio/PipeWire default sink and match sample rate + bit depth.")
    p.add_argument("--show-audio-info", action="store_true",
                   help="Print detected system audio configuration and exit.")

    p.add_argument("--haptic-mode", choices=("none", "constant_carrier", "entrainment_locked"), default="entrainment_locked")
    p.add_argument("--haptic-carrier-hz", type=float, default=40.0)
    p.add_argument("--haptic-amplitude", type=float, default=0.8)

    p.add_argument("--no-photic", action="store_true", help="Disable the photic/light channel entirely.")
    p.add_argument("--photic-waveform", choices=("sine", "square"), default="sine")

    p.add_argument(
        "--acknowledge-risks",
        action="store_true",
        help="Required to render square-wave photic output inside the photosensitive-seizure caution band.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.show_audio_info:
        info = detect_audio_output()
        _print_audio_info(info)
        return 0

    sample_rate = args.sample_rate
    bit_depth = args.bit_depth

    if args.match_system:
        info = detect_audio_output()
        if info.sample_rate:
            sample_rate = info.sample_rate
        if info.matched_bit_depth:
            bit_depth = info.matched_bit_depth
        _print_audio_info(info)
        print(f"  -> Using: {sample_rate} Hz, {bit_depth}-bit")

    protocol = PROTOCOLS[args.protocol](carrier_hz=args.carrier_hz)
    config = SessionConfig(
        audio_mode=args.audio_mode,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        audio_amplitude=args.audio_amplitude,
        haptic_mode=None if args.haptic_mode == "none" else args.haptic_mode,
        haptic_carrier_hz=args.haptic_carrier_hz,
        haptic_amplitude=args.haptic_amplitude,
        photic_enabled=not args.no_photic,
        photic_waveform=args.photic_waveform,
        acknowledge_risks=args.acknowledge_risks,
    )

    try:
        manifest = render_session(protocol, config, args.out_dir)
    except EntrainmentSafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    print(f"Rendered {protocol.name!r} ({protocol.total_duration:.0f}s) -> {args.out_dir}/")
    for f in manifest["files"].values():
        print(f"  {f}")
    for w in manifest["safety_warnings"]:
        print(f"  WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
