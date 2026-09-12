---
tags: [bil, sues]
---

# SUES Slot Syntax

Human-typed compact input format for the [[Architecture|BIL pipeline]]:

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

A SUES frame lowers directly into [[BIL Token Grammar|BIL tokens]] via BIL-IR. Known gap (v0.7): adjective predicates (e.g. "is bright") have no predicate slot mapping yet — see [[Roadmap & Status]].
