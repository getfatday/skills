---
name: dream-team:recruit
description: Recruit a new team-member — research a named expert OR survey candidates for a domain. Auto-bootstraps the bundled catalog on first run.
argument-hint: "<expert name or domain>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebSearch
  - AskUserQuestion
---

<objective>
Add a new team-member to the dream team. If the bundled factory catalog hasn't been installed in this repo yet, auto-bootstrap it first so `/consult`, `/coach`, `/plan`, `/review` work immediately.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/team-member-recruit/SKILL.md`. The skill handles:

1. First-run bootstrap — if `.config/team/root.md` is missing, materialize the full factory catalog (workflow engine + orchestrator + entry commands + 23 bundled members + 2 teams) and write the roster manifest.
2. Mode A — specific person ("Our CTO", "Jane Smith"): research the named expert via the research engine, write the blueprint, emit the materialized persona skill.
3. Mode B — domain or skillset survey ("devops", "find me an SRE expert"): survey 8–10 candidates, score them 0–30, present a multi-select shortlist, then run Mode A inline for each selected expert.

The skill handles mode dispatch — including a clarifying `AskUserQuestion` when the argument is ambiguous (could be a person name or a domain name).
</workflow>
