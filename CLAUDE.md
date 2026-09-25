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

**First, the load-bearing fact:** the BIL token stream is currently **write-only**. `encode_bil_ir` produces it, `n8n_handle` stores and prints it, and nothing ever parses it back — there is no decoder in this file (grep for `decode`: the only hit is a concept-path *string*, not a function). The round-trip that exists, English → BIL-IR → English, runs entirely through the IR JSON; `generate_english()` reads the IR dict, never the tokens. So the three invariants below do **not** break anything today — they make the token stream **non-decodable by construction**, which is what blocks the README roadmap's v0.9 decoder and v1.0 round-trip benchmark, and undercuts the premise that "BIL tokens" are a payload an LLM could recover meaning from. Right now the tokens are a lossy sidecar next to the real payload (the IR).

**None of the three invariants hold** (`tests/test_bil_interpreter.py` pins each as an `@unittest.expectedFailure`):
- **Not delimiter-free:** 14 of 111 tokens contain `C1` or `C2` as one of their own space-separated symbols (e.g. `speech.act.say → "W1 C1 R1"`, `object.symbol.token → "R1 C2 W1"`). `encode_bil_ir` joins slot tokens with `" C1 "` and appends `" C2"`, so a future decoder splitting on the delimiter can't recover the original tokens: encode `speech.act.say` + `entity.person.speaker` → `"W1 C1 R1 C1 R1 W1 C2"`, which no longer splits back into the two source tokens.
- **Not total:** 74 of 183 `SUES_MAP` concepts (~40%) have no `TOKEN_REGISTRY` entry — encoding falls back silently to `UNK_TOKEN[{concept}]`.
- **Not injective:** several token strings are reused across unrelated concepts, so a decoder could not tell them apart, independent of the delimiter issue above.
- `_ENGLISH_LABELS` covers only 35 of 183 concepts (~19%) — `generate_english()` echoes the raw dotted concept path for the rest instead of natural English.
- `ENGLISH_TO_SUES` has ~10 entries pointing at SUES terms that don't exist in `SUES_MAP` (e.g. `tell`, `keepgo`, `@answer`), which `map_sues_term()` silently passes through unresolved.

The README's own roadmap (`v0.8 — ... token collision checker`) already flags this class of bug as unaddressed — it's a known gap, not a surprise. `tests/test_bil_interpreter.py` now exists and encodes all of this: the invariant checks above are real tests marked `@unittest.expectedFailure` (so the suite stays green while documenting the exact defects), plus regression tests for what currently works (ambiguity resolution, SUES parsing, `n8n_handle`'s contract, and the 7/8 README demo-case pass rate). Run it with `python3 -m unittest tests.test_bil_interpreter -v`. If you fix one of the invariants, its test flips to an "unexpected success" — that's your signal to drop the `expectedFailure` marker and lock the fix in. If you're adding vocabulary, check all four dicts by hand and rerun this suite before extending further.

### Status (from README, may drift — verify before relying on it)

SUES parser and BIL-IR schema: stable. Token encoder: runs, but emits a non-decodable stream (see the write-only note above) — treat it as a display artifact, not a recoverable encoding, until a decoder and the three invariants exist. English generator: basic. English parser: lexicon-based, no POS tagging. Round-trip fidelity: English↔IR only; the token layer does not round-trip.

## Vibroacoustic entrainment package

Separate, self-contained, actually tested (stdlib `unittest`, not pytest — pytest isn't installed in this environment). Run `python3 -m unittest tests.test_vibroacoustic_entrainment -v` before changing `vibroacoustic_entrainment/*`.

## design/rock5b/ (Aquila font install tooling)

`install-aquila-font.sh` is a dry-run-by-default bash script that edits real system files (fontconfig, KDE `kdeglobals`, console font) on a physical ROCK 5B — nothing here is unit-testable in the usual sense, and `--apply` should never be run in a sandbox/CI container, since it genuinely writes to `/etc/fonts/conf.d`, `/usr/local/share/fonts`, and calls `apt-get`. `tests/test_rock5b.py` covers what *is* safe to check without a real device or root: `60-aquila.conf` is well-formed XML, the script's bash syntax is valid, and its dry-run argument handling (`--help`, an unknown flag, `--rollback` with no backup) behaves correctly. Run with `python3 -m unittest tests.test_rock5b -v` (never pass `--apply` to the script itself outside a real ROCK 5B).

`60-aquila.conf`'s header comment previously used a literal `--` as a typographic dash, which is illegal inside an XML comment except as the closing `-->` — the same category of bug as the BIL `TOKEN_REGISTRY` delimiter collision above (a reserved delimiter sequence reused as ordinary content). Fixed to use an em dash; `test_is_well_formed_xml` guards against it recurring.
