---
tags: [bil, nlp]
---

# Ambiguity Resolution

The resolver scores candidate word senses by context-clue overlap, per [[BIL Overview#Core rule|BIL's core rule]] that a word maps to a *sense*, not a token, directly.

| Word | Context clue | Resolved sense |
|---|---|---|
| `run` + `program` | `program` | `action.system.operate` |
| `run` + `store` | `store` | `action.motion.run_foot` |
| `bank` + `loan` | `loan` | `finance.institution.bank` |
| `bank` + `river` | `river` | `geography.land.riverbank` |
| `light` + `bright` | `bright` | `object.energy.light` |
| `light` + `carry` | `carry` | `quality.weight.light` |

Status: prototype, clue-based scoring only — see [[Roadmap & Status]] for what full-dictionary coverage (v0.9, WordNet-expanded) would add.
