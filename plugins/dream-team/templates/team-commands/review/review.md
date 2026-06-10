---
tier: 2-materialized
materialized: "2026-06-08"
description: "Team review — multi-member anti-pattern scan and principle alignment check on code, designs, or plans"
pattern-hint: reflection
---

# Team Review

Review work through multiple expert lenses. The orchestrator selects the best conversation pattern, defaulting to reflection (generate-critique-refine) or map-reduce for broad coverage.

## Step 1: Discover Team Members

Scan the consumer's local roster — `.config/team/team-members/*.md`. Each blueprint declares a roster entry; the matching materialized persona lives at `.claude/skills/{slug}/SKILL.md`.

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Identify the Artifact

Parse `$ARGUMENTS` for a file path, PR reference, or description of what to review. If nothing specified, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the artifact's domain to relevant team-members. Propose 2-4 reviewers.
- **"Let me pick"** — present all team-members with `multiSelect: true`.
- **"Everyone"** — all team-members review. Maximum coverage.

## Step 4: Select Pattern

Read `.claude/skills/team-assemble/patterns/router.md` and classify the review task. The `pattern-hint` is `reflection`, but the adaptive router may override:
- Broad review (many aspects) → **map-reduce** (parallel perspectives)
- Quality-critical single artifact → **reflection** (iterative critique-refine)
- Reviewing a decision → **debate** (stress-test the choice)
- Sequential review stages → **sequential** (design → code → test)

Announce the selected pattern to the user.

## Step 5: Run Review

Execute the selected pattern. For each selected team-member:
1. Read its materialized persona at `.claude/skills/{slug}/SKILL.md` and its `.claude/skills/{slug}/references/anti-patterns.md`
2. Read the artifact being reviewed
3. Apply the pattern's flow

Present findings per the pattern's template. After all perspectives, synthesize:

```
## Synthesis
Unanimous concerns: ...
Split opinions: ...
Recommended fixes (priority order): ...
```

The orchestrator monitors for signals (e.g., strong disagreement → escalate to debate).

## Step 6: Continue

Use AskUserQuestion:
- "Apply the fixes" — make changes to the artifact
- "Debate a specific finding" — switch to debate pattern
- "Get a deeper critique" — switch to reflection with a specific critic
- "Dig deeper on a specific finding" — expand one reviewer's feedback
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
