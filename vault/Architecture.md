---
tags: [bil, architecture]
---

# Architecture

The BIL pipeline, end to end:

```
English input
    ↓  normalize
    ↓  SUES term lookup + ambiguity resolution
    ↓  SUES slot frame   (ACT / AGT / PRED / OBJ / STYLE)
    ↓  BIL-IR JSON       (structured semantic frame)
    ↓  BIL token stream  (symbolic encoding)
    ↓  English output    (round-trip generation)
```

Each stage is a separate, inspectable representation — see [[SUES Slot Syntax]] for the slot frame, [[BIL Token Grammar]] for the symbolic layer, and [[n8n Integration]] for how the pipeline is exposed over a webhook.

## Integration Context

BIL is designed as the semantic preprocessing layer for:
- n8n multi-agent orchestration pipelines
- SANd-X local-first AI node
- DocGrok retrieval (intent disambiguation before vector search)
- Any pipeline where natural language ambiguity causes downstream errors

Related: [[BIL Overview]], [[Roadmap & Status]]
