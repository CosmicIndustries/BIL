import array
import json
import math
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibroacoustic_entrainment import (
    Protocol,
    SessionConfig,
    Stage,
    focus21_extended_bridge,
    gateway_focus10,
    hyper_cognition_obe_phase_protocol,
    lucia_hypnagogic,
    render_session,
    vibroacoustic_relaxation,
)
from vibroacoustic_entrainment import oscillators, haptic, photic
from vibroacoustic_entrainment.safety import EntrainmentSafetyError, check_photic_safety


def count_zero_crossings(samples, sample_rate, t0, t1):
    i0 = int(t0 * sample_rate)
    i1 = int(t1 * sample_rate)
    crossings = 0
    for i in range(i0 + 1, i1):
        if (samples[i - 1] <= 0) != (samples[i] <= 0):
            crossings += 1
    return crossings


class ProtocolTests(unittest.TestCase):
    def test_stage_rejects_bad_duration(self):
        with self.assertRaises(ValueError):
            Stage("bad", 0.0, 10.0, 7.0)

    def test_stage_rejects_bad_frequency(self):
        with self.assertRaises(ValueError):
            Stage("bad", 10.0, 0.0, 7.0)

    def test_total_duration_matches_stage_sum(self):
        protocol = Protocol(
            name="t",
            stages=(Stage("a", 5.0, 10.0, 10.0), Stage("b", 3.0, 10.0, 4.0)),
        )
        self.assertAlmostEqual(protocol.total_duration, 8.0)

    def test_freq_at_interpolates_linearly(self):
        protocol = Protocol(name="t", stages=(Stage("a", 10.0, 10.0, 2.0),))
        self.assertAlmostEqual(protocol.freq_at(0.0), 10.0)
        self.assertAlmostEqual(protocol.freq_at(5.0), 6.0, places=5)
        self.assertAlmostEqual(protocol.freq_at(10.0), 2.0, places=5)

    def test_freq_at_flat_stage_is_constant(self):
        protocol = Protocol(name="t", stages=(Stage("a", 4.0, 6.0, 6.0),))
        for t in (0.0, 1.0, 2.0, 3.5, 4.0):
            self.assertAlmostEqual(protocol.freq_at(t), 6.0)

    def test_phase_continuous_across_stage_boundary(self):
        protocol = Protocol(
            name="t",
            stages=(Stage("a", 2.0, 5.0, 5.0), Stage("b", 2.0, 5.0, 5.0)),
        )
        boundary_from_a = protocol.stages[0].phase_at(2.0)
        self.assertAlmostEqual(protocol.phase_at(2.0), boundary_from_a)
        # phase must keep accumulating monotonically into stage b, not reset to 0
        self.assertGreater(protocol.phase_at(2.5), protocol.phase_at(2.0))

    def test_builtin_protocols_construct_and_have_positive_duration(self):
        from vibroacoustic_entrainment.protocol import PROTOCOLS

        for name, builder in PROTOCOLS.items():
            protocol = builder()
            self.assertGreater(protocol.total_duration, 0, msg=name)
            self.assertGreater(protocol.carrier_hz, 0, msg=name)

    def test_obe_phase_protocol_has_extended_plateau(self):
        protocol = hyper_cognition_obe_phase_protocol()
        plateau = [s for s in protocol.stages if s.name == "phase_plateau"][0]
        self.assertEqual(plateau.freq_start, plateau.freq_end)
        self.assertGreaterEqual(plateau.duration_s, 600.0)

    def test_focus21_bridge_dips_below_focus15_floor_and_returns(self):
        protocol = focus21_extended_bridge()
        trough = [s for s in protocol.stages if s.name == "focus21_trough"][0]
        self.assertLess(trough.freq_end, 2.0)
        # last stage should bridge back up toward alpha, not end on the trough
        self.assertGreater(protocol.stages[-1].freq_end, protocol.stages[-1].freq_start)

    def test_lucia_hypnagogic_steps_through_named_band_holds(self):
        protocol = lucia_hypnagogic()
        holds = {s.name: s.freq_start for s in protocol.stages if s.name.endswith("_hold")}
        self.assertAlmostEqual(holds["lucia_delta_hold"], 3.0)
        self.assertAlmostEqual(holds["lucia_theta_hold"], 6.0)
        self.assertAlmostEqual(holds["lucia_alpha_hold"], 10.0)

    def test_vibroacoustic_relaxation_stays_flat_alpha(self):
        protocol = vibroacoustic_relaxation()
        for s in protocol.stages:
            self.assertAlmostEqual(s.freq_start, 10.0)
            self.assertAlmostEqual(s.freq_end, 10.0)
        self.assertGreaterEqual(protocol.total_duration, 1200.0)


class OscillatorTests(unittest.TestCase):
    def test_binaural_left_right_have_different_instantaneous_frequency(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 10.0, 10.0),), carrier_hz=200.0)
        left, right = oscillators.render_binaural(protocol, sample_rate=8000, amplitude=0.9)
        self.assertEqual(len(left), len(right))
        # left carrier = 200 - 5 = 195 Hz, right = 200 + 5 = 205 Hz over 1s window
        left_crossings = count_zero_crossings(left, 8000, 0.1, 0.9)
        right_crossings = count_zero_crossings(right, 8000, 0.1, 0.9)
        # zero crossings ~ 2*f*duration; right should have more than left
        self.assertGreater(right_crossings, left_crossings)

    def test_monaural_produces_amplitude_beat_envelope(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 4.0, 4.0),), carrier_hz=200.0)
        mono = oscillators.render_monaural(protocol, sample_rate=8000, amplitude=0.9)
        self.assertEqual(len(mono), 8000)
        self.assertTrue(any(abs(s) > 0 for s in mono))

    def test_isochronic_gate_silences_between_pulses(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 4.0, 4.0),), carrier_hz=200.0)
        mono = oscillators.render_isochronic(
            protocol, sample_rate=8000, amplitude=0.9, duty_cycle=0.3, edge_ms=1.0
        )
        # somewhere in the track the gate must be near-zero (off phase of the pulse)
        self.assertTrue(any(abs(s) < 50 for s in mono))
        # and somewhere near full amplitude (on phase, at a carrier peak)
        self.assertTrue(any(abs(s) > 32767 * 0.5 for s in mono))

    def test_wav_roundtrip_stereo(self):
        protocol = Protocol(name="t", stages=(Stage("a", 0.5, 10.0, 10.0),))
        left, right = oscillators.render_binaural(protocol, sample_rate=8000)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.wav")
            oscillators.write_wav_stereo(path, left, right, sample_rate=8000)
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getframerate(), 8000)
                self.assertEqual(wf.getnframes(), len(left))


class HapticTests(unittest.TestCase):
    def test_constant_carrier_never_fully_silent(self):
        protocol = Protocol(name="t", stages=(Stage("a", 0.5, 4.0, 4.0),))
        track = haptic.render_haptic_track(protocol, sample_rate=8000, mode="constant_carrier")
        self.assertTrue(any(abs(s) > 1000 for s in track))

    def test_entrainment_locked_has_on_and_off_phases(self):
        protocol = Protocol(name="t", stages=(Stage("a", 2.0, 2.0, 2.0),))
        track = haptic.render_haptic_track(protocol, sample_rate=8000, mode="entrainment_locked")
        self.assertTrue(any(abs(s) > 1000 for s in track))
        self.assertTrue(any(abs(s) < 50 for s in track))

    def test_haptic_envelope_json_monotonic_and_bounded(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 4.0, 4.0),))
        events = haptic.render_haptic_envelope_json(protocol, control_rate_hz=50.0)
        times = [e["t"] for e in events]
        self.assertEqual(times, sorted(times))
        for e in events:
            self.assertGreaterEqual(e["duty"], 0)
            self.assertLessEqual(e["duty"], 255)

    def test_bad_mode_rejected(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 4.0, 4.0),))
        with self.assertRaises(ValueError):
            haptic.render_haptic_track(protocol, mode="not_a_mode")


class PhoticTests(unittest.TestCase):
    def test_sine_waveform_events_bounded(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 10.0, 10.0),))
        events = photic.render_photic_events(protocol, control_rate_hz=60.0, waveform="sine")
        for e in events:
            self.assertGreaterEqual(e["brightness"], 0.0)
            self.assertLessEqual(e["brightness"], 1.0)

    def test_square_wave_in_risk_band_requires_acknowledgement(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 18.0, 18.0),))
        with self.assertRaises(EntrainmentSafetyError):
            photic.render_photic_events(protocol, waveform="square", acknowledge_risks=False)
        # acknowledging renders successfully
        events = photic.render_photic_events(protocol, waveform="square", acknowledge_risks=True)
        self.assertGreater(len(events), 0)

    def test_sine_wave_in_risk_band_does_not_raise(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 18.0, 18.0),))
        events = photic.render_photic_events(protocol, waveform="sine", acknowledge_risks=False)
        self.assertGreater(len(events), 0)

    def test_check_photic_safety_outside_band_is_quiet(self):
        protocol = Protocol(name="t", stages=(Stage("a", 1.0, 2.0, 2.0),))
        warnings = check_photic_safety(protocol, waveform="square", acknowledge_risks=False)
        self.assertEqual(warnings, [])


class SessionTests(unittest.TestCase):
    def test_render_session_writes_all_expected_files(self):
        protocol = gateway_focus10(duration_s=1.0)
        config = SessionConfig(sample_rate=8000, haptic_control_rate_hz=50.0, photic_control_rate_hz=30.0)
        with tempfile.TemporaryDirectory() as d:
            manifest = render_session(protocol, config, d)
            for fname in ("audio.wav", "haptic.wav", "haptic_envelope.json", "photic_events.json", "manifest.json"):
                self.assertTrue(os.path.exists(os.path.join(d, fname)), msg=fname)
            with open(os.path.join(d, "manifest.json")) as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["protocol"], "gateway_focus10")
            self.assertAlmostEqual(on_disk["total_duration_s"], manifest["total_duration_s"])

    def test_render_session_without_haptic_or_photic(self):
        protocol = gateway_focus10(duration_s=1.0)
        config = SessionConfig(haptic_mode=None, photic_enabled=False, sample_rate=8000)
        with tempfile.TemporaryDirectory() as d:
            render_session(protocol, config, d)
            self.assertFalse(os.path.exists(os.path.join(d, "haptic.wav")))
            self.assertFalse(os.path.exists(os.path.join(d, "photic_events.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "audio.wav")))

    def test_render_session_blocks_unacknowledged_risky_square_photic(self):
        protocol = Protocol(name="risky", stages=(Stage("a", 1.0, 18.0, 18.0),))
        config = SessionConfig(photic_waveform="square", acknowledge_risks=False, sample_rate=8000)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(EntrainmentSafetyError):
                render_session(protocol, config, d)

    def test_output_path_stays_within_output_dir(self):
        from vibroacoustic_entrainment.session import _output_path

        with tempfile.TemporaryDirectory() as d:
            resolved = _output_path(d, "audio.wav")
            self.assertEqual(os.path.dirname(resolved), os.path.realpath(d))

    def test_output_path_rejects_traversal(self):
        from vibroacoustic_entrainment.session import _output_path

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                _output_path(d, "../escaped.wav")


class AudioOutputTests(unittest.TestCase):
    def test_parse_sink_name(self):
        from vibroacoustic_entrainment.audio_output import _parse_sink_name

        text = "Server Name: PipeWire\nDefault Sink: alsa_output.pci-0000_00_1f.3.hdmi-stereo\n"
        self.assertEqual(_parse_sink_name(text), "alsa_output.pci-0000_00_1f.3.hdmi-stereo")

    def test_parse_sink_name_missing(self):
        from vibroacoustic_entrainment.audio_output import _parse_sink_name

        self.assertIsNone(_parse_sink_name(None))
        self.assertIsNone(_parse_sink_name("no match here"))

    def test_parse_sinks_short(self):
        from vibroacoustic_entrainment.audio_output import _parse_sinks_short

        text = "60\talsa_output.pci-0000_00_1f.3.hdmi-stereo\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
        result = _parse_sinks_short(text, "alsa_output.pci-0000_00_1f.3.hdmi-stereo")
        self.assertEqual(result["sample_rate"], 48000)
        self.assertEqual(result["channels"], 2)
        self.assertEqual(result["sample_format"], "s32le")
        self.assertEqual(result["bit_depth"], 32)

    def test_parse_sinks_short_no_match(self):
        from vibroacoustic_entrainment.audio_output import _parse_sinks_short

        text = "60\tother_sink\tPipeWire\ts16le 2ch 44100Hz\tRUNNING\n"
        self.assertEqual(_parse_sinks_short(text, "nonexistent_sink"), {})

    def test_parse_volume(self):
        from vibroacoustic_entrainment.audio_output import _parse_volume

        text = "Volume: front-left: 26214 /  40% / -23.88 dB,   front-right: 26214 /  40% / -23.88 dB\n"
        self.assertEqual(_parse_volume(text), 40)

    def test_parse_mute(self):
        from vibroacoustic_entrainment.audio_output import _parse_mute

        self.assertFalse(_parse_mute("Mute: no"))
        self.assertTrue(_parse_mute("Mute: yes"))
        self.assertIsNone(_parse_mute(None))

    def test_parse_server(self):
        from vibroacoustic_entrainment.audio_output import _parse_server

        text = "Server Name: PipeWire (version 1.0)\nDefault Sink: foo\n"
        self.assertEqual(_parse_server(text), "PipeWire (version 1.0)")

    def test_audio_output_info_matched_bit_depth(self):
        from vibroacoustic_entrainment.audio_output import AudioOutputInfo

        self.assertEqual(AudioOutputInfo(bit_depth=32).matched_bit_depth, 32)
        self.assertEqual(AudioOutputInfo(bit_depth=16).matched_bit_depth, 16)
        self.assertEqual(AudioOutputInfo(bit_depth=24).matched_bit_depth, 32)
        self.assertEqual(AudioOutputInfo(bit_depth=None).matched_bit_depth, 16)

    def test_pactl_format_bits_coverage(self):
        from vibroacoustic_entrainment.audio_output import PACTL_FORMAT_BITS

        self.assertEqual(PACTL_FORMAT_BITS["s32le"], 32)
        self.assertEqual(PACTL_FORMAT_BITS["s16le"], 16)
        self.assertEqual(PACTL_FORMAT_BITS["s24le"], 24)
        self.assertEqual(PACTL_FORMAT_BITS["float32le"], 32)


class BitDepth32Tests(unittest.TestCase):
    def _short_protocol(self):
        return Protocol(
            name="short",
            stages=(Stage("a", 0.5, 10.0, 10.0),),
            carrier_hz=200.0,
        )

    def test_pcm32_conversion(self):
        samples = [0.0, 0.5, -0.5, 1.0, -1.0]
        result = oscillators._to_pcm32(samples)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 5 * 4)
        import struct
        vals = [struct.unpack("<i", result[i*4:(i+1)*4])[0] for i in range(5)]
        self.assertEqual(vals[0], 0)
        self.assertGreater(vals[1], 0)
        self.assertLess(vals[2], 0)

    def test_render_binaural_32bit(self):
        p = self._short_protocol()
        left, right = oscillators.render_binaural(p, sample_rate=8000, bit_depth=32)
        self.assertIsInstance(left, bytes)
        self.assertIsInstance(right, bytes)
        self.assertEqual(len(left), len(right))
        n = oscillators._n_samples(0.5, 8000)
        self.assertEqual(len(left), n * 4)

    def test_render_monaural_32bit(self):
        p = self._short_protocol()
        mono = oscillators.render_monaural(p, sample_rate=8000, bit_depth=32)
        self.assertIsInstance(mono, bytes)
        n = oscillators._n_samples(0.5, 8000)
        self.assertEqual(len(mono), n * 4)

    def test_render_isochronic_32bit(self):
        p = self._short_protocol()
        mono = oscillators.render_isochronic(p, sample_rate=8000, bit_depth=32)
        self.assertIsInstance(mono, bytes)

    def test_write_wav_mono_32bit(self):
        p = self._short_protocol()
        mono = oscillators.render_monaural(p, sample_rate=8000, bit_depth=32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            oscillators.write_wav_mono(path, mono, 8000, sample_width=4)
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 4)
                self.assertEqual(wf.getframerate(), 8000)
        finally:
            os.unlink(path)

    def test_write_wav_stereo_32bit(self):
        p = self._short_protocol()
        left, right = oscillators.render_binaural(p, sample_rate=8000, bit_depth=32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            oscillators.write_wav_stereo(path, left, right, 8000, sample_width=4)
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 4)
                self.assertEqual(wf.getframerate(), 8000)
        finally:
            os.unlink(path)

    def test_session_config_rejects_bad_bit_depth(self):
        with self.assertRaises(ValueError):
            SessionConfig(bit_depth=24)

    def test_render_session_32bit(self):
        protocol = gateway_focus10(duration_s=0.5)
        config = SessionConfig(
            sample_rate=8000, bit_depth=32,
            haptic_mode=None, photic_enabled=False,
        )
        with tempfile.TemporaryDirectory() as d:
            manifest = render_session(protocol, config, d)
            audio_path = os.path.join(d, "audio.wav")
            with wave.open(audio_path, "rb") as wf:
                self.assertEqual(wf.getsampwidth(), 4)
                self.assertEqual(wf.getframerate(), 8000)
                self.assertEqual(wf.getnchannels(), 2)

    def test_render_session_32bit_monaural(self):
        protocol = gateway_focus10(duration_s=0.5)
        config = SessionConfig(
            audio_mode="monaural", sample_rate=8000, bit_depth=32,
            haptic_mode=None, photic_enabled=False,
        )
        with tempfile.TemporaryDirectory() as d:
            manifest = render_session(protocol, config, d)
            audio_path = os.path.join(d, "audio.wav")
            with wave.open(audio_path, "rb") as wf:
                self.assertEqual(wf.getsampwidth(), 4)
                self.assertEqual(wf.getnchannels(), 1)

    def test_render_session_32bit_isochronic(self):
        protocol = gateway_focus10(duration_s=0.5)
        config = SessionConfig(
            audio_mode="isochronic", sample_rate=8000, bit_depth=32,
            haptic_mode=None, photic_enabled=False,
        )
        with tempfile.TemporaryDirectory() as d:
            manifest = render_session(protocol, config, d)
            audio_path = os.path.join(d, "audio.wav")
            with wave.open(audio_path, "rb") as wf:
                self.assertEqual(wf.getsampwidth(), 4)
                self.assertEqual(wf.getnchannels(), 1)


class CLITests(unittest.TestCase):
    def test_cli_bit_depth_flag(self):
        from vibroacoustic_entrainment.cli import build_parser

        args = build_parser().parse_args(["--bit-depth", "32"])
        self.assertEqual(args.bit_depth, 32)

    def test_cli_match_system_flag(self):
        from vibroacoustic_entrainment.cli import build_parser

        args = build_parser().parse_args(["--match-system"])
        self.assertTrue(args.match_system)

    def test_cli_show_audio_info_flag(self):
        from vibroacoustic_entrainment.cli import build_parser

        args = build_parser().parse_args(["--show-audio-info"])
        self.assertTrue(args.show_audio_info)


if __name__ == "__main__":
    unittest.main()
