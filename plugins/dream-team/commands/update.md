---
name: dream-team:update
description: Sync the materialized dream-team artifacts in this repo with the installed plugin — re-materialize drifted files, run schema migrations, clean up orphans.
argument-hint: "[slug]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Bulk drift sync. Brings materialized dream-team files current with the installed plugin.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
This command is a router. The selected skill depends on `$ARGUMENTS`:

**No argument** → route to `skills/team-update/SKILL.md`. The skill scans
the repo via `scripts/upgrade-scan.py`, presents a per-artifact action
plan, and resolves each drift mode declaratively (re-materialize stale,
sweep orphans, run schema migrations, refuse to downgrade `ahead`
artifacts, skip hand-edited/detached files).

**A slug argument** (e.g. `/dream-team:update kent-beck`) →
classify the slug via `scripts/upgrade-scan.py` first. The JSON has a
`slug` key on every artifact; route on the entry where
`kind == "skill"` matches the requested slug:

- `classification: current` → `skills/team-member-update/SKILL.md` —
  the user wants **intellectual** enrichment, not a file refresh. Ask
  in natural language what new material to incorporate (book, talk,
  blog series) and run the research-driven flow.
- `classification: stale` with `reason_codes` containing
  `blueprint-hash-drift` (and not `factory-version-drift`) →
  `skills/team-update/SKILL.md` scoped to the slug — the user has hand-edited
  the blueprint and just needs the materialized files refreshed.
- `classification: stale` with `factory-version-drift`, or
  `orphan`, `migration-needed` → `skills/team-update/SKILL.md` scoped
  to the slug — file-drift resolution that doesn't require research.
- `classification: ahead | detached | untracked | malformed` → refuse,
  surface the classification, and direct the user.

Natural-language phrasings ("update Kent Beck with his new book
Tidy First") trigger `team-member-update` directly without going through
this command — they carry the new-material description in the prompt.
The slash command exists for the discovery case where the user just
types `/dream-team:update <slug>` and lets the router decide.

`team-update` handles **file drift**. `team-member-update` handles
**intellectual drift**. The two never overlap.
</workflow>
