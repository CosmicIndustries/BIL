# Vibroacoustic + Haptovisual Entrainment Engine

`vibroacoustic_entrainment/` is a self-contained Python package that renders
brainwave-entrainment sessions — synchronized audio, tactile ("haptic"), and
strobe/LED ("photic") tracks — from a shared frequency-ramp schedule. It targets the
same alpha → theta → delta descent structure the Monroe Institute's Hemi-Sync
"Gateway Process" publicly describes, including a plateau protocol aimed at the
extended low-theta hold that out-of-body-experience ("OBE"/"phasing") induction
literature associates with the reported "vibrational stage."

**Read the [Disclaimers & safety](#disclaimers--safety) section before pointing this
at real hardware.**

## Research this is built on

### Monroe Institute — Hemi-Sync and the Gateway Process

Robert Monroe's Monroe Institute developed "Hemi-Sync" (Hemispheric Synchronization),
a binaural-beat-based audio process, and packaged a sequence of guided exercises —
the **Gateway Process** — around it. The process moves a listener through named
"Focus levels," each associated with a described EEG character:

| Focus level | Description (as publicly stated by Monroe Institute materials) | Approximate frequency character |
|---|---|---|
| Focus 10 | "Mind Awake, Body Asleep" | Alpha (~10 Hz) descending toward theta border (~7 Hz) |
| Focus 12 | Expanded awareness | Theta (~7 → 4 Hz) |
| Focus 15 | "No Time" | Theta/delta border (~4 → 2 Hz) |
| Focus 21 | "The Bridge" | Described qualitatively, no public canonical frequency |

The Monroe Institute's actual Hemi-Sync signal-processing chain is proprietary and
not published. The frequency schedules in `protocol.py` (`gateway_focus10`,
`gateway_focus12`, `gateway_focus15`, `gateway_full_progression`) are **this
project's own interpretation** of the publicly described Focus-level structure,
built independently — not a reproduction of the Monroe Institute's proprietary
algorithm, and not officially affiliated with or endorsed by the Monroe Institute.
The declassified 1983 CIA report *"Analysis and Assessment of Gateway Process"*
(released under FOIA) is a useful public account of the program's theoretical
framing; it is not a technical specification of Hemi-Sync's DSP.

### Binaural beats, monaural beats, isochronic tones

* **Binaural beat** — two slightly-detuned pure tones, one per ear. The beat
  frequency (the difference between them) is synthesized in the brainstem, not
  physically present in the air; requires headphones.
* **Monaural beat** — the same two tones summed before the ear, so the beat is a
  physically real amplitude-modulated waveform; works on speakers.
* **Isochronic tone** — a single tone pulsed on/off at the target frequency.
  Comparative EEG work from David Siever and Mind Alive Inc. reports isochronic
  pulsing drives a stronger Frequency Following Response (FFR) than binaural beats
  at matched intensity — the basis for `audio_mode="isochronic"`.

### Vibroacoustic therapy (the haptic channel)

Norwegian therapist Olav Skille's **Physioacoustic Method** (from the late 1970s/early
1980s onward) applied low-frequency sound (not audible tone — felt vibration) directly
to the body via tactile transducers, in the **30–120 Hz** range, with **40 Hz** cited
most often as the best-tolerated default for relaxation and reduced muscle
tension/spasticity. That characterized range is where this package's
`haptic.DEFAULT_TACTILE_CARRIER_HZ = 40.0` and `safety.VIBROACOUSTIC_RECOMMENDED_BAND
= (30.0, 120.0)` come from. Modern vibroacoustic chairs/mats and Monroe's own "CHEC
unit" cushion are the same class of hardware this channel is meant to drive.

### Audio-visual entrainment and hypnagogic light machines (the photic channel)

"Audio-visual entrainment" (AVE) devices (e.g. Mind Alive's David-series, built on
David Siever's research) pair pulsed light with pulsed/beating audio, reporting a
stronger combined photic-driving response than either modality alone. **Lucia N°03**
(developed by neurologist Dirk Proeckl and psychologist Engelbert Winkler) is a
purpose-built strobing light machine marketed for inducing a "hypnagogic" state —
the threshold between waking and sleep associated with hypnagogic imagery, deep
meditation, and (per its own marketing and user reports) OBE-adjacent experiences.
Photic driving — an EEG-measurable response time-locked to a flicker's frequency — is
real and well documented; whether it reliably produces a subjectively meaningful
altered state, let alone an OBE, is not.

### OBE / "phasing" induction literature

Robert Monroe's own account in *Journeys Out of the Body* and Robert Bruce's
*Astral Dynamics* both describe a **"vibrational stage"**: a period of holding a
relaxed-but-alert, low-arousal state (not falling asleep) while a strong, rhythmic,
full-body sensory pulse is present, reportedly preceding a dissociative "roll
out"/"phase shift" experience. `protocol.hyper_cognition_obe_phase_protocol()` models
that *shape* — Focus 10 → Focus 12 → an extended flat ~4 Hz plateau — paired with
`haptic_mode="entrainment_locked"` (a rhythmic full-body pulse) and a synchronized
photic track, as an engineering analog of "hold the state while the pulse runs."
**This is a self-exploration protocol modeled on practitioner literature, not a
validated neuroscience protocol, and the engine makes no claim that it produces an
OBE or any specific cognitive state.**

## Architecture

```
Protocol (frequency-vs-time schedule, in Hz, ramped per Stage)
    │
    ├── oscillators.py   → audio.wav        (binaural / monaural / isochronic)
    ├── haptic.py         → haptic.wav        (tactile-transducer PCM signal)
    │                      → haptic_envelope.json (PWM duty-cycle stream for a
    │                                                microcontroller-driven motor rig)
    └── photic.py         → photic_events.json (LED/strobe brightness keyframes)

session.py renders all of the above from one Protocol + SessionConfig into a
manifest.json describing stage boundaries, config, and safety warnings — the
common clock a playback rig lines all three tracks up against.
```

The key correctness property: every channel's phase comes from
`Protocol.phase_at(t)`, the **closed-form integral** of the (possibly ramping)
frequency schedule — not a per-sample running accumulator — so a multi-minute
frequency sweep never introduces phase discontinuities (audible clicks, or a photic
event train that drifts out of sync with the audio) at stage boundaries or across
the whole render.

## Usage

```bash
python3 -m vibroacoustic_entrainment.cli --protocol obe_phase --out-dir out/
```

```python
from vibroacoustic_entrainment import PROTOCOLS, SessionConfig, render_session

protocol = PROTOCOLS["obe_phase"]()
manifest = render_session(protocol, SessionConfig(audio_mode="isochronic"), "out/")
```

Available `--protocol` values: `focus10`, `focus12`, `focus15`, `gateway` (chained
10→12→15), `obe_phase` (10→12→extended theta plateau).

## Disclaimers & safety

* **Not medical devices, not clinical protocols.** This is a self-directed
  relaxation/meditation/exploration tool. Nothing here is validated for treating any
  condition.
* **Photosensitive epilepsy.** Flashing light in roughly the **3–60 Hz** band is the
  internationally recognized caution range for photosensitive seizures, peaking
  around 15–20 Hz. `photic.py` defaults to a **sine** brightness waveform (no
  harmonics, lower risk per epilepsy-safety guidance); switching to `"square"` (hard
  strobe) inside that band raises `EntrainmentSafetyError` unless the caller passes
  `acknowledge_risks=True` (`--acknowledge-risks` on the CLI). Passing that flag is
  not a safety measure — it's a "I have confirmed this is appropriate" gate. Do not
  use the photic channel, sine or square, if you or the intended user has
  photosensitive epilepsy, migraine with visual aura, or any other flash sensitivity.
* **Cardiac devices / vibration sensitivity.** The haptic channel drives a real
  tactile transducer with continuous low-frequency vibration for the session
  duration. Consult a clinician first if the user has an implanted cardiac device,
  is pregnant, or has a condition where sustained low-frequency vibration is
  contraindicated.
* **Drowsiness.** These are low-arousal, eyes-closed, lying-down sessions by design.
  `safety.check_session_duration` warns past 90 minutes; use a spotter/attendant for
  longer sessions, and never use this while operating a vehicle or otherwise needing
  to stay alert.
* **Headphones required for `audio_mode="binaural"`.** The binaural beat only forms
  perceptually when each ear gets its own channel; on speakers use `"monaural"` or
  `"isochronic"` instead.

## Status

| Component | Status |
|---|---|
| Frequency-schedule protocol engine (`protocol.py`) | Stable |
| Binaural / monaural / isochronic audio render (`oscillators.py`) | Stable |
| Haptic tactile-transducer + PWM envelope render (`haptic.py`) | Stable |
| Photic strobe/LED keyframe render (`photic.py`) | Stable |
| Safety checks (photosensitive band, VAT band, duration) (`safety.py`) | Prototype — covers the specific hazards called out above, not a general safety certification |
| Session orchestration + manifest (`session.py`) | Stable |
| CLI (`cli.py`) | Stable |

Not yet implemented: a live playback rig driver (this engine renders files; wiring
`haptic_envelope.json`/`photic_events.json` to a specific microcontroller or LED
goggle is left to the hardware integration), and EEG-feedback closed-loop control
(all schedules here are open-loop/pre-rendered).
