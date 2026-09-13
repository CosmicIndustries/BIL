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
# Install the HTTP client dependency (only needed for adapters.py / server.py)
pip install -r requirements.txt

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

## HTTP Adapters (`adapters.py`)

Outbound HTTP calls to LLM providers and n8n webhooks use [httpx](https://www.python-httpx.org/) rather than `requests` or raw `urllib`, per `plan.md`'s adapter layer:

```python
from adapters import call_openai, call_claude, forward_to_n8n

call_openai(bil_tokens, model="gpt-4o-mini")   # OPENAI_API_KEY env var, or pass api_key=
call_claude(bil_tokens, model="claude-sonnet-5")  # ANTHROPIC_API_KEY env var, or pass api_key=
forward_to_n8n(webhook_url, n8n_handle(payload))  # relay a round-trip result to an n8n webhook
```

Each function opens a short-lived `httpx.Client` with explicit connect/read/write/pool timeouts and raises on non-2xx responses — there's no retry/backoff logic yet (see `plan.md`'s rate-limit notes for what that should look like).

---

## Local Server + Browser Userscript

`server.py` exposes `n8n_handle` over HTTP with the stdlib (`http.server`, no new dependency — httpx is a client, not a server) so you can hit the interpreter without standing up n8n:

```bash
python3 server.py
# BIL webhook server listening on http://127.0.0.1:8787/bil

curl -X POST http://127.0.0.1:8787/bil \
    -H 'Content-Type: application/json' \
    -d '{"input_type": "english", "input_text": "Fix the code."}'
```

`userscript/bil-helper.user.js` is a Tampermonkey/Violentmonkey script: select text on any page, press **Alt+B**, and it POSTs the selection to the server above and shows the output text + BIL tokens in a small overlay next to your selection. The endpoint defaults to `http://127.0.0.1:8787/bil` and is configurable via the script's Tampermonkey menu command ("Set BIL endpoint").

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
| HTTP adapters (OpenAI/Claude/n8n) | ⚠️ Basic, no retries |
| Local server + userscript | ✅ Prototype |

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

*Part of the SANd-X ecosystem.*
