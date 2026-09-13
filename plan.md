# BIL System — Architecture Plan

## Executive Summary

A two-layer BIL system: a structured meaning layer (BIL-IR) and a compact token layer. Incoming text is first parsed into a JSON-like AST ("BIL-IR") capturing intent, roles, context and constraints. This is then encoded into a short symbolic token stream (the "BIL tokens") which can be passed to an LLM or Q&A bot. The bot's BIL-token response is decoded back into BIL-IR and realized as natural language. Orchestrated via n8n using a Webhook trigger and HTTP request nodes.

---

## Key Elements

### BIL-IR Schema

JSON objects with fields like `speech_act`, `agent`, `target`, `predicate`, `constraints`, etc.

```json
{
  "speech_act": "request",
  "intent": "schedule_constraint",
  "agent": "USER",
  "target": "MANAGER",
  "predicate": "avoid_pairing",
  "avoid_entity": "TINA",
  "modality": {"tone": "professional", "urgency": 0.7},
  "constraints": {"avoid": ["insults"], "prefer": ["neutral"]}
}
```

Structured frames eliminate ambiguity by forcing explicit fields. Define via JSON Schema or Pydantic models for consistency. Speech acts (request/warning/apology) follow linguistics conventions.

### Ontology / Lexicon

Extensible vocabulary module containing:
- Canonical semantic roles (Agent, Patient, Action)
- Tags (speech acts, domains, risk levels, tone)
- New content words / roles map to unique morphemes or semantic IDs
- Updatable for new domains (synonyms, new action primitives)

### Parser: NL → BIL-IR

Hybrid approach recommended:

| Approach | Pros | Cons |
|---|---|---|
| Rule-based NLU | Fast, deterministic for fixed patterns | Brittle; misses unseen phrasing |
| ML/LLM NLU | Flexible, handles ambiguity | Needs training data or compute |
| Hybrid (LLM + Rules) | Best coverage and control | More complex architecture |

Fallback: if intent confidence < 40%, trigger clarification or use `None` intent.

### Encoder / Decoder: BIL-IR ↔ Tokens

Deterministic mapping from IR fields to tokens. Example token stream:

```
SIG.USER  ACT.REQUEST  OBJ.SCHEDULE  NEG.PAIR  ENTITY.TINA  REASON.CONFLICT  TONE.PROF
```

Encoded as BIL tokens: `C1 R2 W1 R1 W3 C1 ...`

Unknown elements reported as raw text for manual handling.

### Generator: BIL-IR → NL

Rule-based template strings or LLM prompt. Example template:

```
"[Agent] requests [target] to avoid [entity] at [event] because [reason]."
```

### Data Flow

```
User
 ↓  NL text
n8n Webhook
 ↓
Parser: NL → BIL-IR
 ↓
Encoder: BIL-IR → Tokens
 ↓
AI Bot (OpenAI / Claude)
 ↓
Decoder: Tokens → BIL-IR
 ↓
Generator: BIL-IR → NL
 ↓
n8n Webhook Response
 ↓
User
```

---

## n8n Integration

**Authentication:**
- OpenAI: `Authorization: Bearer <key>`
- Claude: `X-API-Key` + `anthropic-version` header

**Rate limiting:** monitor `x-ratelimit-remaining-requests`, exponential backoff on 429.

**Minimal n8n workflow nodes:**
1. `WebhookTrigger` — POST `/bil`
2. `ParseAndEncode` — Function node (parser + encoder)
3. `CallOpenAI` or `CallClaude` — HTTP Request node
4. `DecodeAndGenerate` — Function node (decoder + generator)
5. `Respond` — RespondToWebhook node

---

## Minimal Prototype Tech Stack

**Python package `bil/`:**
- `schema.py` — IR dataclasses / JSON schema
- `ontology.py` — vocab lists, roles, tags
- `parser.py` — NL → IR (spaCy + rules)
- `encoder.py` / `decoder.py` — IR ↔ tokens
- `generator.py` — IR → NL templates
- `validators.py` — IR validity checks

**Adapters `bil/adapters/`:**
- `openai.py`, `claude.py`, `n8n.py`

**Tests `tests/`:**
- `test_roundtrip.py`

**Frameworks:** Pydantic (schema validation), spaCy (rule parsing), OpenAI Python SDK.

---

## Design Trade-offs

| Component | Option | Pros | Cons |
|---|---|---|---|
| Parser | Rule-based | Predictable, low compute | Brittle |
| | ML/LLM-based | Captures nuance | Requires GPU / data |
| | Hybrid | Best coverage | Complex |
| Token Format | Alphanumeric tags | Human-readable | Larger token count |
| | Numeric codes | Compact | Harder to interpret |
| | Binary/compressed | Smallest payload | Complex encode/decode |
| Transport | HTTP + JSON | Standard, n8n-friendly | JSON overhead |
| | HTTP + plain text | Simple | Manual parsing |
| | WebSockets | Low latency | Unnecessary complexity |

---

## Testing Strategy

- **Roundtrip tests:** Input → Parser → Encoder → Decoder → Generator → output; verify semantic equivalence
- **Meaning preservation:** negations, coreferences, multi-sentence edge cases
- **Edge cases:** unknown words, out-of-vocab terms, mixed languages, incomplete frames
- **Stress tests:** high-volume throughput, simulated rate-limit errors via mocking

---

## MVP Roadmap

1. Define BIL-IR schema → `schema.py`
2. Basic parser + encoder → `parser.py`, `encoder.py`
3. n8n workflow setup — minimal Webhook→Function→HTTP→Function→Respond
4. Integrate LLM (OpenAI / Claude nodes)
5. Roundtrip test suite → `test_roundtrip.py`
6. Expand lexicon and semantic frames
7. Deployment prep — containerize n8n, logging, rate-limit retries
8. Pilot + iterate

**Target:** working prototype in 2–4 weeks. Expand BIL vocabulary and robustness from there.

---

*BIL's core value: forces explicit semantics — communicates meaning, not words — dramatically reducing ambiguity for AI agents.*

