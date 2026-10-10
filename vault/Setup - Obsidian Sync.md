---
tags: [meta, setup]
---

# Setup - Obsidian Sync

This vault is the `vault/` folder inside the `CosmicIndustries/BIL` git repo. It syncs through git using the **Obsidian Git** community plugin — no separate note-taking service involved.

## First-time setup (per machine)

1. Clone the repo somewhere local, e.g.:
   ```bash
   git clone git@github.com:CosmicIndustries/BIL.git
   ```
2. In Obsidian, **Open folder as vault** → select the `BIL/vault` subfolder (not the repo root — the root also holds the Python interpreter and isn't meant to be a vault).
3. Settings → Community plugins → turn off Restricted mode → Browse → install **Obsidian Git** → Enable.
4. Settings → Obsidian Git, recommended config:
   - **Vault backup interval (minutes)**: `10` (auto-commit + push on a timer)
   - **Pull updates on startup**: on
   - **Push on backup**: on
   - **Commit message**: `vault backup: {{date}}` (default is fine)
   - **Auto pull interval**: `10`

This repo's `.gitignore` (in `vault/`) already excludes Obsidian's local workspace/cache files (`workspace.json`, `.trash/`, plugin caches) so those never conflict across machines — only your actual notes and the shared plugin list sync.

## Branch note

Claude's own work on this repo lands on `claude/*` branches and merges to `main` via PR. Point your local Obsidian Git remote/branch at whichever branch you're actually using day-to-day (usually `main` once these seed notes are merged) so you're not fighting an in-review branch.

## Conflicts

Obsidian Git does a merge pull, not a rebase — if you and a Claude session edit the same note before syncing, git will leave conflict markers in that note. Resolve them like any merge conflict (Obsidian shows the raw `<<<<<<<`/`=======`/`>>>>>>>` text in the editor) and commit.
