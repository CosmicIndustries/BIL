# CLAUDE.md

Orientation for working in this repo. It hosts several unrelated projects under one roof — check which one you're touching before assuming conventions carry over.

## Repo layout

| Path | Project | Status |
|---|---|---|
| `bil_v07_interpreter.py` | BIL interpreter (see below) | Active, zero automated tests |
| `vibroacoustic_entrainment/` | Standalone Python package, brainwave-entrainment audio/haptic engine | Has tests (`tests/test_vibroacoustic_entrainment.py`) |
| `design/` | Aquila design system (CSS tokens, style guide, Rock5B font install) | Docs + assets, no build step |
| `userscripts/cosmic-otf-youtube.user.js` | Browser userscript | Standalone |
| `plan.md` | Original BIL architecture plan | Historical — describes a `bil/` package (`schema.py`/`parser.py`/`encoder.py`/...) that was never built; everything instead landed in the single `bil_v07_interpreter.py` file. Don't treat it as current design. |

No CI, no `pyproject.toml`/`requirements.txt`, no project-level `.claude/settings.json` yet. If you add dependencies beyond the stdlib, add a requirements file at that point.

## BIL interpreter (`bil_v07_interpreter.py`)

Pipeline: `English → normalize → SUES terms (word-sense disambiguation) → SUES slot frame → BIL-IR (JSON) → BIL token stream → English`.

Core rule the whole design hinges on: **word = token is wrong; word sense = semantic concept = token path is correct.** The same surface word (`run`, `bank`, `light`) resolves to different `TOKEN_REGISTRY` concepts depending on context clues (see `AMBIGUOUS` / `resolve_ambiguous_word`).

Run it:
```bash
python3 bil_v07_interpreter.py                              # demo, 8 cases
python3 bil_v07_interpreter.py --english "Run the program."
python3 bil_v07_interpreter.py --sues "ACT:!askdo AGT:@self PRED:partmake OBJ:BIL.partnet"
python3 bil_v07_interpreter.py --english "Fix the code." --json
```

### The four hand-maintained dictionaries

Everything is driven by four dicts in this one file, kept in sync **by hand** — there is no generator script and no consistency test:

| Dict | Line | Maps |
|---|---|---|
| `SUES_MAP` | ~47 | SUES term (`@self`, `!askdo`) → concept path (`entity.person.speaker`) |
| `TOKEN_REGISTRY` | ~273 | concept path → BIL token string (e.g. `"R1 W1"`) |
| `ENGLISH_TO_SUES` | ~415 | English word → SUES term |
| `_ENGLISH_LABELS` | ~887 | concept path → English surface form (decode direction) |

`TOKEN_REGISTRY` is supposed to hold three invariants (this is also documented in the `bil-interpreter` skill): **injective** (each token maps back to exactly one concept), **delimiter-free** (no token may contain the `C1`/`C2` symbols used as the encoder's slot-separator/terminator), and **total** (every concept `SUES_MAP` can produce has a token).

**As of the last audit, none of the three hold**, and there's no test catching it:
- **Not delimiter-free (breaks round-trips today):** 14 of 111 tokens contain `C1` or `C2` as one of their own space-separated symbols (e.g. `speech.act.say → "W1 C1 R1"`, `object.symbol.token → "R1 C2 W1"`). `encode_bil_ir` joins slot tokens with `" C1 "` and appends `" C2"`, so any of these 14 concepts corrupts the slot boundaries on decode. Reproduce: encode `speech.act.say` + `entity.person.speaker` → `"W1 C1 R1 C1 R1 W1 C2"`; splitting on the intended delimiter yields garbage, not the original 2 tokens.
- **Not total:** 74 of 183 `SUES_MAP` concepts (~40%) have no `TOKEN_REGISTRY` entry — encoding falls back silently to `UNK_TOKEN[{concept}]`.
- **Not injective:** several token strings are reused across unrelated concepts, so decode is ambiguous for those independent of the delimiter issue above.
- `_ENGLISH_LABELS` covers only 35 of 183 concepts (~19%) — `generate_english()` echoes the raw dotted concept path for the rest instead of natural English.
- `ENGLISH_TO_SUES` has ~10 entries pointing at SUES terms that don't exist in `SUES_MAP` (e.g. `tell`, `keepgo`, `@answer`), which `map_sues_term()` silently passes through unresolved.

The README's own roadmap (`v0.8 — ... token collision checker`) already flags this class of bug as unaddressed — it's a known gap, not a surprise. If you're adding vocabulary, check all four dicts by hand, and ideally add the collision/coverage checks above as a real test (`tests/test_bil_interpreter.py` — doesn't exist yet) before extending further, since nothing currently guards against making it worse.

### Status (from README, may drift — verify before relying on it)

SUES parser and BIL-IR schema: stable. Token encoder: stable *modulo the collision bug above*. English generator: basic. English parser: lexicon-based, no POS tagging. Round-trip fidelity: partial.

## Vibroacoustic entrainment package

Separate, self-contained, actually tested (stdlib `unittest`, not pytest — pytest isn't installed in this environment). Run `python3 -m unittest tests.test_vibroacoustic_entrainment -v` before changing `vibroacoustic_entrainment/*`.
