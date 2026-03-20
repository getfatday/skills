---
description: "Team coaching — guided walkthrough with expert avatars, learn by applying their frameworks to your situation"
---

# Team Coach

Get coached through a practice or concept by your avatar team. Each avatar teaches using their own frameworks, with their own voice.

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/avatar-*/AVATAR.md`
- Glob `~/.claude/plugins/marketplaces/*/plugins/avatar-*/AVATAR.md`
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Understand What to Learn

Parse `$ARGUMENTS` for the topic, practice, or concept the user wants coaching on. If unclear, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the topic to relevant avatars. Propose 2-4 coaches who cover this area.
- **"Let me pick"** — present all avatars with `multiSelect: true`.
- **"Everyone"** — all avatars coach. Round-table teaching.

## Step 4: Coaching Session

For each selected avatar:
1. Read its `AVATAR.md` fully
2. The avatar introduces the concept from THEIR perspective, using THEIR voice
3. The avatar walks the user through applying it to their actual situation
4. Use AskUserQuestion at each step to keep the user engaged

If multiple avatars:
- Each takes a turn coaching the same topic from their angle
- After all perspectives, highlight where they agree and where they differ
- Let the user ask follow-up questions directed at specific avatars

**Coaching format per avatar:**
```
## {Avatar Name}'s Coaching

**The concept:** {how this avatar frames it}
**Why it matters:** {grounded in their principles}
**Let's apply it:** {walk through the user's specific situation}
**Watch out for:** {anti-patterns relevant to this concept}
```

## Step 5: Continue

Use AskUserQuestion:
- "Practice this with my code/project" — hands-on application
- "Hear from another expert" — add an avatar to the session
- "Go deeper on {avatar}'s approach" — 1:1 deep dive
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
