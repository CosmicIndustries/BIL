# BIL v0.7 Interpreter

**Biophonic Intermediary Language** — a semantic disambiguation layer between natural language and AI processing pipelines.

---

## What It Is

BIL is a two-layer semantic encoding system:

| Layer | Name | Purpose |
|---|---|---|
| Surface | **SUES** — Semantic Unit Encoding Syntax | Compact human-readable semantic notation |
| Formal | **BIL-IR** — BIL Intermediate Representation | Structured JSON meaning frame |
| Symbolic | **BIL tokens** | Compressed symbolic token stream |

**Core rule:**

```
WRONG  → word = token
CORRECT → word sense = semantic concept = token path
```

The same word maps to different concepts depending on sense. `run the program` → `action.system.operate`. `run to the store` → `action.motion.run_foot`.

---

## Architecture

```
English input
    ↓  normalize
    ↓  SUES term lookup + ambiguity resolution
    ↓  SUES slot frame   (ACT / AGT / PRED / OBJ / STYLE)
    ↓  BIL-IR JSON       (structured semantic frame)
    ↓  BIL token stream  (symbolic encoding)
    ↓  English output    (round-trip generation)
```

---

## Quick Start

```bash
# Run demo (8 test cases)
python3 bil_v07_interpreter.py

# Single English input
python3 bil_v07_interpreter.py --english "Run the program."

# SUES slot input (direct)
python3 bil_v07_interpreter.py --sues "ACT:!askdo AGT:@self PRED:partmake OBJ:BIL.partnet STYLE:stepclear+technical OUT:codeout"

# Raw JSON output
python3 bil_v07_interpreter.py --english "Fix the code." --json
```

---

## SUES Slot Syntax

Human-typed compact input format:

```
ACT:<speech_act> AGT:<agent> PRED:<predicate> OBJ:<object> STYLE:<style+style> OUT:<format>
```

| Slot | Description | Example values |
|---|---|---|
| `ACT` | Speech act | `!askdo` `!do` `?ask` `whyshow` `say` |
| `AGT` | Agent/doer | `@self` `@you` `@we` |
| `PRED` | Predicate/action | `partmake` `workagain` `bettermake` |
| `OBJ` | Object/theme | `codedo` `partnet` `infobits` |
| `STYLE` | Output style (stackable with `+`) | `stepclear+technical` |
| `OUT` | Output format | `codeout` `jsonout` `pdfout` |

---

## Ambiguity Resolution

The resolver scores candidate senses by context clue overlap:

| Word | Context clue | Resolved sense |
|---|---|---|
| `run` + `program` | `program` | `action.system.operate` |
| `run` + `store` | `store` | `action.motion.run_foot` |
| `bank` + `loan` | `loan` | `finance.institution.bank` |
| `bank` + `river` | `river` | `geography.land.riverbank` |
| `light` + `bright` | `bright` | `object.energy.light` |
| `light` + `carry` | `carry` | `quality.weight.light` |

---

## BIL Token Grammar

| Token | Type | Meaning |
|---|---|---|
| `R1` `R2` `R3` | Rumble | noun root / entity / negation/weight |
| `W1` `W2` `W3` | Whistle | verb/action / process / future/abstraction |
| `C1` | Delimiter | phrase separator |
| `C2` | Delimiter | sentence terminator |
| `G1` | Modifier | question / rising |
| `G2` | Modifier | command / directive |
| `ST1–ST10` | Style | output style tokens |
| `OUT0–OUT5` | Format | output format tokens |

---

## n8n Integration

```json
{
  "thread_id": "bil-demo",
  "input_type": "english",
  "input_text": "Please help me build a better BIL system."
}
```

Response contract:

```json
{
  "ok": true,
  "thread_id": "bil-demo",
  "bil_ir": { ... },
  "bil_tokens": "G2 W1 R2 C1 R1 W1 C1 ...",
  "output_text": "Please help me build the BIL system.",
  "validation": { "valid": true, "errors": [], "warnings": [] },
  "ambiguity_report": [ ... ]
}
```

Call `n8n_handle(payload)` directly or wire the file as a Python node.

---

## Status

| Component | Status |
|---|---|
| SUES slot parser | ✅ Stable |
| BIL-IR schema | ✅ Stable |
| Ambiguity resolver | ✅ Prototype (clue-based scoring) |
| Token encoder | ✅ Stable |
| English generator | ⚠️ Basic (predicate/object surface form) |
| English parser | ⚠️ Lexicon-based (no POS tagger or dependency parse) |
| Full English dictionary | ❌ Not yet (WordNet compiler pending) |
| Round-trip fidelity | ⚠️ Predicate/object preserved; complex clauses partial |

**v0.7 passes 7/8 demo cases.** Known gap: adjective predicates (e.g. "is bright") have no predicate slot mapping yet.

---

## Roadmap

- **v0.8** — AST parser, nested clauses, conditional frames, token collision checker
- **v0.9** — WordNet-expanded full English dictionary compiler
- **v1.0** — Production n8n workflow JSON, full round-trip benchmark suite

---

## Integration Context

BIL is designed as the semantic preprocessing layer for:
- n8n multi-agent orchestration pipelines
- SANd-X local-first AI node
- DocGrok retrieval (intent disambiguation before vector search)
- Any pipeline where natural language ambiguity causes downstream errors

---

## Design System

Any UI built around BIL (docs sites, n8n dashboards, companion apps) should use the **Aquila design system** — an ADHD- and dyslexia-friendly accessible theme. See [`design/AQUILA_STYLE_GUIDE.md`](design/AQUILA_STYLE_GUIDE.md) for tokens, rationale, and a live demo.

---

*Part of the SANd-X ecosystem.*

