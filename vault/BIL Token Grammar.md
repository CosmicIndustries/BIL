---
tags: [bil, tokens]
---

# BIL Token Grammar

The symbolic layer at the end of the [[Architecture|pipeline]]:

| Token | Type | Meaning |
|---|---|---|
| `R1` `R2` `R3` | Rumble | noun root / entity / negation-weight |
| `W1` `W2` `W3` | Whistle | verb/action / process / future-abstraction |
| `C1` | Delimiter | phrase separator |
| `C2` | Delimiter | sentence terminator |
| `G1` | Modifier | question / rising |
| `G2` | Modifier | command / directive |
| `ST1`–`ST10` | Style | output style tokens |
| `OUT0`–`OUT5` | Format | output format tokens |

Encoded from a [[SUES Slot Syntax|SUES slot frame]] via BIL-IR. Token encoder is stable as of v0.7 — see [[Roadmap & Status]].
