---
tier: 2-materialized
materialized: "2026-06-08"
description: "Team plan — multi-member planning with domain-specific gray areas, decomposition, and verification criteria"
pattern-hint: supervisor
---

# Team Plan

Create a plan informed by multiple expert perspectives. The orchestrator selects the best conversation pattern, defaulting to supervisor (task decomposition with specialist delegation).

## Step 1: Discover Team Members

Scan the consumer's local roster — `.config/team/team-members/*.md`. Each blueprint declares a roster entry; the matching materialized persona lives at `.claude/skills/{slug}/SKILL.md`.

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Understand the Goal

Parse `$ARGUMENTS` for what needs to be planned. If unclear, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the goal to relevant domains. Propose 2-4 planners.
- **"Let me pick"** — present all team-members with `multiSelect: true`.
- **"Everyone"** — all team-members contribute. Maximum perspective.

## Step 4: Select Pattern

Read `.claude/skills/team-assemble/patterns/router.md` and classify the planning task. The `pattern-hint` is `supervisor`, but the adaptive router may override:
- Brainstorming phase → **round-robin** (collaborative building)
- Complex nested problem → **hierarchical** (recursive decomposition)
- Unclear problem space → **blackboard** (emergent exploration)
- Need broad input first → **map-reduce** then narrow

Announce the selected pattern to the user.

## Step 5: Gather Gray Areas

For each selected team-member:
1. Read its materialized persona at `.claude/skills/{slug}/SKILL.md` and its `.claude/skills/{slug}/references/principles.md`
2. Generate 2-3 gray area questions that team-member would ask BEFORE planning
3. Present all gray areas grouped by team-member

Walk through each gray area with AskUserQuestion to lock decisions.

## Step 6: Build the Plan

Execute the selected pattern to build the plan:

- **Decomposition**: each team-member suggests how to break the work down
- **Verification criteria**: each team-member contributes what "done" looks like from their lens
- **Anti-pattern warnings**: flag risks each team-member would watch for

The orchestrator monitors for signals and may switch patterns mid-planning.

Present the integrated plan.

## Step 7: Continue

Use AskUserQuestion:
- "Execute this plan" — begin implementation
- "Adjust the plan" — modify before starting
- "Debate a specific decision" — switch to debate pattern on a contentious point
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
