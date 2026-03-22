---
description: "Team coaching — guided walkthrough with expert avatars, learn by applying their frameworks to your situation"
pattern-hint: sequential
---

# Team Coach

Get coached through a practice or concept by your avatar team. The orchestrator selects the best conversation pattern, defaulting to sequential (progressive learning through stages).

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/marketplaces/*/plugins/dream-team/avatars/*/AVATAR.md`
- Glob `plugins/dream-team/avatars/*/AVATAR.md` (within the plugin)
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Understand What to Learn

Parse `$ARGUMENTS` for the topic, practice, or concept the user wants coaching on. If unclear, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the topic to relevant avatars. Propose 2-4 coaches who cover this area.
- **"Let me pick"** — present all avatars with `multiSelect: true`.
- **"Everyone"** — all avatars coach. Round-table teaching.

## Step 4: Select Pattern

Read `patterns/router.md` and classify the coaching task. The `pattern-hint` is `sequential`, but the adaptive router may override:
- Single concept, one expert → **moe-routing** (deep 1:1 coaching)
- Multiple perspectives needed → **round-robin** (each coach takes a turn, building on prior)
- Broad overview first → **map-reduce** (parallel takes, then synthesize)
- Concept has debate → **debate** (coaches argue approaches, user learns from the tension)

Announce the selected pattern to the user.

## Step 5: Coaching Session

Execute the selected pattern. For each selected avatar:
1. Read its `AVATAR.md` fully
2. The avatar introduces the concept from THEIR perspective, using THEIR voice
3. The avatar walks the user through applying it to their actual situation
4. Use AskUserQuestion at each step to keep the user engaged

**Coaching format per avatar:**
```
## {Avatar Name}'s Coaching

**The concept:** {how this avatar frames it}
**Why it matters:** {grounded in their principles}
**Let's apply it:** {walk through the user's specific situation}
**Watch out for:** {anti-patterns relevant to this concept}
```

The orchestrator monitors for signals (e.g., user is confused → slow down and go deeper with one expert).

## Step 6: Continue

Use AskUserQuestion:
- "Practice this with my code/project" — hands-on application
- "Hear from another expert" — add an avatar to the session
- "Go deeper on {avatar}'s approach" — switch to moe-routing for 1:1 deep dive
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
