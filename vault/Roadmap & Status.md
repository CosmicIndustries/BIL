---
tags: [bil, roadmap, status]
---

# Roadmap & Status

## Status (v0.7)

| Component | Status |
|---|---|
| SUES slot parser | ✅ Stable |
| BIL-IR schema | ✅ Stable |
| Ambiguity resolver | ✅ Prototype (clue-based scoring) — [[Ambiguity Resolution]] |
| Token encoder | ✅ Stable — [[BIL Token Grammar]] |
| English generator | ⚠️ Basic (predicate/object surface form) |
| English parser | ⚠️ Lexicon-based (no POS tagger or dependency parse) |
| Full English dictionary | ❌ Not yet (WordNet compiler pending) |
| Round-trip fidelity | ⚠️ Predicate/object preserved; complex clauses partial |

v0.7 passes 7/8 demo cases. Known gap: adjective predicates (e.g. "is bright") have no predicate slot mapping yet — see [[SUES Slot Syntax]].

## Roadmap

- **v0.8** — AST parser, nested clauses, conditional frames, token collision checker
- **v0.9** — WordNet-expanded full English dictionary compiler
- **v1.0** — Production n8n workflow JSON, full round-trip benchmark suite ([[n8n Integration]])

## Repo Hygiene

- `README.md` and `plan.md` on `main` currently have unresolved git merge-conflict markers from a bad merge — fixes are pending in [PR #2](https://github.com/CosmicIndustries/BIL/pull/2) and [PR #3](https://github.com/CosmicIndustries/BIL/pull/3). Once one merges, refresh [[BIL Overview]] and [[Architecture]] against the cleaned files if they drift.
