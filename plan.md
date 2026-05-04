<<<<<<< HEAD
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
=======

Executive Summary

We propose a two-layer BIL system: a structured meaning layer (BIL-IR) and a compact token layer. Incoming text is first parsed into a JSON-like AST (“BIL-IR”) capturing intent, roles, context and constraints. This is then encoded into a short symbolic token stream (the “BIL tokens”) which can be passed to an LLM or Q&A bot. The bot’s BIL-token response is decoded back into BIL-IR and realized as natural language. We integrate this in an n8n workflow using a Webhook trigger and HTTP request nodes to handle API calls.

Key elements:

    BIL-IR Schema: JSON objects with fields like speech_act, agent, target, predicate, constraints, etc. For example, a request might become:

    json

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

    This structured frame eliminates ambiguity by forcing explicit fields (e.g. intent, tone). We recommend defining such schema via JSON Schema or Pydantic models (as Microsoft’s Semantic Kernel does) to ensure consistency. All fields (e.g. speech acts like request/warning/apology) follow linguistics conventions.

    Ontology/Lexicon: Maintain an extensible vocabulary and ontology module. It contains canonical semantic roles (e.g. Agent, Patient, Action) and tags (speech acts, domains, risk levels, tone). New content words or roles map to unique morphemes or semantic IDs. For example, a lexicon entry might map "avoid_pairing" → ["AV", "ID"] in tokens, or directly to the IR predicate. We also include speech-act labels (requests, assertions, questions, etc) and context tags (e.g. HR-sensitive, legal context). This lexicon should be updatable (e.g. by adding synonyms or new action primitives) to handle new domains.

    Parser (NL → BIL-IR): We suggest a hybrid approach. A rule-based component (using regex or dependency patterns) can extract explicit mentions (names, time phrases, simple intents), while an ML component (LLM or trained classifier) resolves more subtle intent and roles. We recommend using LLM-based parsing with a JSON schema prompt (per OpenAI’s structured output guide) or a tool like spaCy/Transformer NLU. Fallback: If intent confidence is low (e.g. <40%), the workflow triggers a default action (e.g. ask for clarification or use a “None” intent). For example:
    Approach	Pros	Cons
    Rule-based NLU	Fast, deterministic for fixed patterns	Brittle; misses unseen phrasing or context
    ML/LLM NLU	Flexible, handles ambiguity and nuance	Needs training data or heavy compute; opaque
    Hybrid (LLM+Rules)	Combines precision and flexibility; fallback paths	More complex; requires integration of components

    By combining them, we get reliability and coverage. For uncertainty, we check model confidence or parse score and default to generic parsing (or human review) if below threshold.

    Encoder/Decoder (BIL-IR ↔ Tokens): The encoder serializes a BIL-IR JSON into a linear token stream. We define a deterministic mapping (e.g. a fixed dictionary or function) from IR fields to tokens. For compression, we use short symbols (like “AV” for avoid, “SIG.USER” for identity) or even numeric codes. The decoder reverses this mapping to reconstruct the IR (allowing minor errors). We enforce signatures by prepending speaker IDs (to indicate source identity). We validate the stream for unknown tokens or invalid sequences. For example:

    plaintext

    SIG.USER   ACT.REQUEST   OBJ.SCHEDULE   NEG.PAIR   ENTITY.TINA   REASON.CONFLICT   TONE.PROF

    could be encoded as tokens like C1 R2 W1 R1 W3 C1 ... (our earlier gibbon-inspired mapping). Error checking ensures we only use defined tokens; unknown elements are reported as raw text for manual handling.

    Generator (BIL-IR → NL): Converts a semantic frame back to text. This can be rule-based (template strings) or use an LLM prompt. E.g. fill a template: “[Agent] requests [target] to avoid [entity] at [event] because [reason].” Or prompt an LLM with: “Rewrite the following request in professional tone: ...” based on BIL-IR fields. Using a structured prompt (potentially with function-calling or JSON schema) ensures clarity. We may use small grammar libraries or string templates for common patterns to keep output consistent.

    n8n + API Adapters: We orchestrate via n8n (an open-source workflow tool). An HTTP Webhook node triggers the workflow on user input. We set up an n8n OpenAI node (or generic HTTP Request node) to call ChatGPT/Claude. - The OpenAI node uses the official Node integration, which wraps the Chat Completion or Responses API (sending the BIL token string as prompt). - For Claude, we use n8n’s HTTP Request node with custom headers (x-api-key, anthropic-version). Authentication: OpenAI requires Authorization: Bearer <key> and Claude requires X-API-Key plus version. We store keys as n8n credentials (or environment vars) for security. We must handle rate limits (OpenAI/Claude provide headers like x-ratelimit-remaining-requests) by batching or backoff.

    Data Flow & Formats: See below for a data-flow diagram. Input JSON (from webhook) contains the raw text. The parser outputs BIL-IR (JSON), which is encoded to tokens. We send a JSON payload to the bot, e.g. {"model":"gpt-4o","prompt": "<BIL tokens>"}, or use a structured input if supported (function calls). The bot returns a JSON (Chat Completion or Claude response) with tokens, which we decode. Finally n8n responds with a JSON or text payload back to the client. For example, an n8n Webhook might return:

    json

    { "reply": "i love you. we will eat food." }

    after the round-trip. n8n’s Webhook node lets us configure the response code, format, and even a “Respond to Webhook” node to send the final output.

mermaid

flowchart LR
    U[User] -->|Submit NL text| N8[n8n Webhook]
    N8 --> Parser[Parser: NL→BIL-IR]
    Parser --> BILIR[BIL-IR JSON]
    BILIR --> Encoder[Encoder: BIL-IR→Tokens]
    Encoder --> Tokens[BIL Token Stream]
    Tokens --> Bot[AI Bot (OpenAI/Claude)]
    Bot --> Tokens2[BIL Token Stream (response)]
    Tokens2 --> Decoder[Decoder: Tokens→BIL-IR]
    Decoder --> BILIR2[BIL-IR JSON (response)]
    BILIR2 --> Generator[Generator: BIL-IR→NL]
    Generator --> NLOut[Natural Language]
    NLOut --> N8
    N8 -->|Respond| U

    Testing Strategy: We will unit-test each component:
        Roundtrip Tests: Input → Parser → Encoder → Decoder → Generator → output, and verify semantic equivalence (ignoring minor phrasing differences).
        Meaning Preservation: For various edge cases (negations, coreferences, multi-sentence), assert the IR fields remain correct.
        Edge Cases: Unknown words should either trigger errors or be passed through. We test out-of-vocab terms, mixed languages, and incomplete frames.
        Example tests: a sentence with multiple clauses, or slang, and see if fallback triggers.
        We’ll write tests in Python (pytest) under tests/, e.g. test_roundtrip.py, verifying end-to-end integrity. Stress tests: feed large volumes to check performance. We can also simulate rate-limit errors by mocking the API.

    Deployment Considerations:
        Scalability: n8n can be self-hosted or on n8n.cloud; ensure it can handle concurrent webhooks. Use horizontal scaling or Kubernetes for high load.
        Logging & Monitoring: Log each step’s data (IR and tokens) with unique message IDs. Use the OpenAI x-request-id and a custom X-Client-Request-Id for tracing. Store logs securely (avoid sensitive user text).
        Security & Privacy: Keep API keys secret (n8n credentials). Sanitize PII – we may encrypt or strip personally identifying data in IR (e.g. replace real names with IDs). Comply with regulations by not storing raw user content beyond needed logs.
        Error Handling: On API failure or parse error, n8n should catch exceptions and return a user-friendly error or retry. Use n8n’s “Error Workflow” or custom error nodes.
        Rate Limiting: Both OpenAI and Claude have RPM/TPM limits. We should monitor headers (e.g. x-ratelimit-remaining-requests) and implement exponential backoff on 429 errors. n8n’s “Delay” node can schedule retries.

    Minimal Prototype (Tech Stack):
        Backend Code (Python): A package bil/ with modules:
            schema.py (defines IR dataclasses/JSON schema),
            ontology.py (vocab lists, roles, tags),
            parser.py (NL→IR logic, e.g. using spaCy and simple rules),
            encoder.py & decoder.py (IR↔tokens),
            generator.py (IR→NL templates),
            validators.py (check IR validity).
            Adapters in bil/adapters/: openai.py (wraps OpenAI API calls), claude.py (wraps Claude API calls), n8n.py (helper to format webhook responses).
            Tests in tests/.
        Frameworks: Use Pydantic (for IR schema validation), Hugging Face Transformers or OpenAI’s Python SDK for any ML models, and spaCy for rule parsing.
        n8n Workflow: Build an n8n workflow (importable as JSON) with:
            Webhook Trigger node.
            Code/Function node calling our parser and encoder (or use n8n’s Python node).
            HTTP Request (OpenAI) node sending BIL tokens,
            Code node for decoder and generator,
            Respond to Webhook node to output.
        Example Code Snippet (Parser):

        python

        # parser.py (simplified)
        def parse_to_bil_ir(text: str) -> dict:
            # naive rule-based example
            bil = {"speech_act": "unknown", "predicates": [], "entities": []}
            if "please" in text.lower():
                bil["speech_act"] = "request"
            # extract some key words
            if "with tina" in text.lower():
                bil["avoid_entity"] = "TINA"
            # ... (use NLP or regex for more)
            return bil

        n8n Workflow JSON: (abridged example)

        json

        {
          "nodes": [
            {
              "name": "WebhookTrigger",
              "type": "n8n-nodes-base.webhook",
              "parameters": {"httpMethod": "POST","path": "bil"},
              ...
            },
            {
              "name": "ParseAndEncode",
              "type": "n8n-nodes-base.function",
              "parameters": {
                "functionCode": "const bil_ir = parseToBILIR($json.text);\nreturn { bil_ir: bil_ir, tokens: encode(bil_ir) };"}
            },
            {
              "name": "CallOpenAI",
              "type": "n8n-nodes-base.openAI",
              "parameters": {"resource": "chatCompletion","operation": "create",...,
                "messages": [{"role": "user", "content": "BIL:"+ {{$json.tokens}} }] }
            },
            {
              "name": "DecodeAndGenerate",
              "type": "n8n-nodes-base.function",
              "parameters": {"functionCode": "const bil_response = decode($json.choices[0].message.content);\nconst reply = generateNL(bil_response);\nreturn { reply };"}
            },
            {
              "name": "Respond",
              "type": "n8n-nodes-base.respondToWebhook",
              "parameters": {"responseCode": 200, "responseData": "={{ { reply: $json.reply } }}"}
            }
          ],
          "connections": {
            "WebhookTrigger": {"main": [[{"node":"ParseAndEncode","type":"main","index":0}]]},
            "ParseAndEncode": {"main": [[{"node":"CallOpenAI","type":"main","index":0}]]},
            "CallOpenAI": {"main": [[{"node":"DecodeAndGenerate","type":"main","index":0}]]},
            "DecodeAndGenerate": {"main": [[{"node":"Respond","type":"main","index":0}]]}
          }
        }

        This shows the data flowing through parsing, API call, decoding, and response.

    Design Alternatives: Below are some trade-off comparisons:
    Component	Options	Pros	Cons
    Parser	Rule-based	Predictable, low compute	Hard to scale, brittle
    	ML/LLM-based	Captures nuance, easy to extend	Requires data/cloud GPU
    	Hybrid (LLM+rules)	Best coverage and control	More complex architecture
    Token Format	Alphanumeric tags (e.g. “C1, R2”)	Human-readable, easy debug	Larger token count
    	Numeric codes (IDs)	Compact, language-neutral	Harder to interpret
    	Binary/compressed	Smallest payload	Complex encode/decode
    Transport	HTTP+JSON (webhook)	Standard, n8n-friendly	Some overhead for JSON tags
    	HTTP+plain text	Very simple (send text body)	Must parse text manually
    	WebSockets/Streaming	Low latency for real-time loops	Unnecessary complexity here

    Component Relationships: Below is a high-level architecture diagram of system modules:

AI Services

Core BIL Modules

Workflow

UserApps

User Interface

n8n Workflow

Parser

Encoder

HTTPReq

Decoder

Generator

BIL-IR Schema / Ontology

OpenAI

Claude

    Next Steps / MVP Plan:
        Define BIL-IR Schema: Draft JSON schema for frames (speech_act, roles, constraints). Code schema.py.
        Basic Parser/Encoder: Implement simple parser with a few intents and static mappings to tokens. Write parser.py and encoder.py.
        n8n Workflow Setup: Build a minimal n8n flow (Webhook→Function→HTTP Request→Function→Respond). Test with a dummy bot (echo service).
        Integrate LLM: Replace dummy with OpenAI/Claude nodes. Use test credentials; handle auth.
        Roundtrip Testing: Write tests (test_roundtrip.py) to ensure IR → tokens → IR is consistent.
        Expand Lexicon & Frames: Add more intents, roles, language patterns. Use feedback loops.
        Deployment Prep: Containerize n8n, set up logs/monitoring, secure keys, configure rate-limit retries.
        Pilot & Iterate: Deploy to small user set, collect errors, refine.

By building in iterations and writing thorough tests, we can have a working prototype quickly (say MVP in 2–4 weeks), then expand the BIL vocabulary and robustness. Ultimately, BIL’s power lies in forcing explicit semantics: it dramatically reduces ambiguity for AI agents by communicating meaning, not words.

Sources: We drew on official n8n docs for webhooks and nodes, and OpenAI/Claude API guides for auth and rate limiting. Speech-act theory and NLU best practices informed our design of intents and confidence fallbacks.
docs.n8n.io
>>>>>>> a8687f534788a1b728c5c49bf7afb513f32c309f
