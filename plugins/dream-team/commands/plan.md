---
description: "Team plan — multi-avatar planning with domain-specific gray areas, decomposition, and verification criteria"
pattern-hint: supervisor
---

# Team Plan

Create a plan informed by multiple expert perspectives. The orchestrator selects the best conversation pattern, defaulting to supervisor (task decomposition with specialist delegation).

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/marketplaces/*/plugins/dream-team/avatars/*/AVATAR.md`
- Glob `plugins/dream-team/avatars/*/AVATAR.md` (within the plugin)
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Understand the Goal

Parse `$ARGUMENTS` for what needs to be planned. If unclear, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the goal to relevant domains. Propose 2-4 planners.
- **"Let me pick"** — present all avatars with `multiSelect: true`.
- **"Everyone"** — all avatars contribute. Maximum perspective.

## Step 4: Select Pattern

Read `patterns/router.md` and classify the planning task. The `pattern-hint` is `supervisor`, but the adaptive router may override:
- Brainstorming phase → **round-robin** (collaborative building)
- Complex nested problem → **hierarchical** (recursive decomposition)
- Unclear problem space → **blackboard** (emergent exploration)
- Need broad input first → **map-reduce** then narrow

Announce the selected pattern to the user.

## Step 5: Gather Gray Areas

For each selected avatar:
1. Read its `AVATAR.md` and its `skills/{avatar-name}/references/principles.md`
2. Generate 2-3 gray area questions that avatar would ask BEFORE planning
3. Present all gray areas grouped by avatar

Walk through each gray area with AskUserQuestion to lock decisions.

## Step 6: Build the Plan

Execute the selected pattern to build the plan:

- **Decomposition**: each avatar suggests how to break the work down
- **Verification criteria**: each avatar contributes what "done" looks like from their lens
- **Anti-pattern warnings**: flag risks each avatar would watch for

The orchestrator monitors for signals and may switch patterns mid-planning.

Present the integrated plan.

## Step 7: Continue

Use AskUserQuestion:
- "Execute this plan" — begin implementation
- "Adjust the plan" — modify before starting
- "Debate a specific decision" — switch to debate pattern on a contentious point
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
