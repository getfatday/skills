---
description: "Team plan — multi-avatar planning with domain-specific gray areas, decomposition, and verification criteria"
---

# Team Plan

Create a plan informed by multiple expert perspectives. Each avatar contributes domain-specific gray areas, decomposition strategies, and verification criteria.

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/avatar-*/AVATAR.md`
- Glob `~/.claude/plugins/marketplaces/*/plugins/avatar-*/AVATAR.md`
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Understand the Goal

Parse `$ARGUMENTS` for what needs to be planned. If unclear, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the goal to relevant domains. Propose 2-4 planners.
- **"Let me pick"** — present all avatars with `multiSelect: true`.
- **"Everyone"** — all avatars contribute. Maximum perspective.

## Step 4: Gather Gray Areas

For each selected avatar:
1. Read its `AVATAR.md` and `references/principles.md`
2. Generate 2-3 gray area questions that avatar would ask BEFORE planning
3. Present all gray areas grouped by avatar

Walk through each gray area with AskUserQuestion to lock decisions.

## Step 5: Build the Plan

With gray areas resolved, create a plan that incorporates each avatar's perspective:

- **Decomposition**: each avatar suggests how to break the work down (Beck: TDD-influenced, Martin: SOLID-informed, Kim: value-stream-based, etc.)
- **Verification criteria**: each avatar contributes what "done" looks like from their lens
- **Anti-pattern warnings**: flag risks each avatar would watch for

Present the integrated plan.

## Step 6: Continue

Use AskUserQuestion:
- "Execute this plan" — begin implementation
- "Adjust the plan" — modify before starting
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
