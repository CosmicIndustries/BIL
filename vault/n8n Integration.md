---
tags: [bil, n8n, integration]
---

# n8n Integration

Request:

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

Call `n8n_handle(payload)` directly, or wire `bil_v07_interpreter.py` as an n8n Python node. Part of the broader [[Architecture|BIL/SANd-X integration context]].
