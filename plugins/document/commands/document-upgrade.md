---
name: document:upgrade
description: Bring a repo's document-plugin artifacts current with the installed plugin — installs available templates, regenerates stale skills, migrates config, confirms hand-edits, refuses to downgrade ahead artifacts
argument-hint: "[--dry-run] [--repo <path>]"
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
Lifecycle command for document-plugin artifacts in a consuming repo. One
pass: detect drift across every state (available, stale, hand-edited,
migration-needed, orphan, ahead, detached), present a plan, and apply with
explicit confirmation. Read-mostly: never silently overwrites a hand-edited
file, refuses to downgrade-regenerate an `ahead` artifact, runs migrations
forward-only. After a fresh repo's first run, it has self-sufficient
`/document-events`, `/document-enrich`, `/document-lint`, and
`/document-verify-inferred` commands that work with no plugin installed.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-upgrade/SKILL.md`:

- `/document:upgrade` → scan, plan, confirm, apply.
- `/document:upgrade --dry-run` → scan and present the plan without acting.
- `/document:upgrade --repo <path>` → operate on a repo other than the cwd.

The skill shells out to `scripts/upgrade-scan.py` (deterministic drift
scan) and `scripts/materialize.py` (template installation), then runs the
judgment loop (hand-edit detection via `document-define regenerate`,
per-file confirmation, schema migrations).
</workflow>
