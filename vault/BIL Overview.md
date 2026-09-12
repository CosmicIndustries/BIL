---
tags: [bil, overview]
---

# BIL Overview

**Biophonic Intermediary Language** — a semantic disambiguation layer between natural language and AI processing pipelines.

BIL is a two-layer semantic encoding system:

| Layer | Name | Purpose |
|---|---|---|
| Surface | SUES — Semantic Unit Encoding Syntax | Compact human-readable semantic notation |
| Formal | BIL-IR — BIL Intermediate Representation | Structured JSON meaning frame |
| Symbolic | BIL tokens | Compressed symbolic token stream |

**Core rule:**

```
WRONG  → word = token
CORRECT → word sense = semantic concept = token path
```

The same word maps to different concepts depending on sense. `run the program` → `action.system.operate`. `run to the store` → `action.motion.run_foot`. See [[Ambiguity Resolution]] for how the resolver picks a sense.

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

See also: [[Architecture]], [[SUES Slot Syntax]], [[BIL Token Grammar]], [[Roadmap & Status]].
