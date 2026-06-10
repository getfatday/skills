---
name: dream-team:roster
description: Show the dream-team roster — installed members, teams, workflow files, and any drift (stale, orphaned, hand-edited, schema-mismatched). Read-only.
argument-hint: ""
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

<objective>
Read-only status report of every materialized dream-team artifact.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/team-roster/SKILL.md`. The skill scans the repo via
`scripts/upgrade-scan.py`, groups artifacts by classification, and prints
a status summary covering installed members, teams, workflow files, and
needs-attention items. Doesn't modify anything — points the user at
`/dream-team:update` or `team-member-remove` for any resolution.
</workflow>
