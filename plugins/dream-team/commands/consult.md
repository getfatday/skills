---
description: "Team consultation — get expert perspectives from your avatar team on any question"
---

# Team Consult

Get expert guidance from your avatar team. The orchestrator recommends relevant avatars, or you pick who to include.

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/avatar-*/AVATAR.md`
- Glob `~/.claude/plugins/marketplaces/*/plugins/avatar-*/AVATAR.md`
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Select Team

Use AskUserQuestion to let the user choose a selection mode:

**Options:**
- **"Auto-select (Recommended)"** — orchestrator analyzes the question, maps to domains, proposes the most relevant 2-4 avatars. User confirms.
- **"Let me pick"** — present all available avatars with `multiSelect: true`. User chooses.
- **"Everyone"** — include all installed avatars. Full panel.

If auto-select: match `$ARGUMENTS` against each avatar's `domains[]`. Rank by relevance. Propose top 2-4. Present via AskUserQuestion for confirmation.

## Step 3: Run Consultation

For each selected avatar:
1. Read its `AVATAR.md` fully (principles, voice, anti-patterns, vocabulary)
2. Respond to the user's question **in that avatar's voice and perspective**
3. Cite which principles support the response
4. Flag any anti-patterns detected

If multiple avatars are selected, present each perspective in sequence under a header with the avatar's name. After all perspectives, synthesize:

```
## Synthesis
Where the avatars agree: ...
Where they diverge: ...
Recommended action: ...
```

## Step 4: Continue

Use AskUserQuestion:
- "Dig deeper with one of these experts" — transition to 1:1 with a specific avatar
- "Get a different team's take" — re-run selection
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
