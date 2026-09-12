---
tags: [bil, moc]
---

# BIL Vault

Entry point for notes on the **Biophonic Intermediary Language (BIL)** project. This vault is the `vault/` folder of the [[CosmicIndustries/BIL]] repo — it syncs to GitHub via the Obsidian Git plugin. See [[Setup - Obsidian Sync]] if you're setting this up on a new machine.

## Map of Content

- [[BIL Overview]] — what BIL is, the core rule, quick start commands
- [[Architecture]] — the English → SUES → BIL-IR → tokens → English pipeline
- [[SUES Slot Syntax]] — the human-typed compact input format
- [[Ambiguity Resolution]] — how word senses get disambiguated
- [[BIL Token Grammar]] — the symbolic token table
- [[n8n Integration]] — webhook contract for the n8n handler
- [[Roadmap & Status]] — what's stable, what's a known gap, what's next

## Open Threads

- Two open PRs (#2, #3) fix unresolved git merge-conflict markers left in `README.md`/`plan.md` on `main` — don't re-derive notes from those files until one merges.
- v0.7 known gap: adjective predicates (e.g. "is bright") have no predicate slot mapping yet.
