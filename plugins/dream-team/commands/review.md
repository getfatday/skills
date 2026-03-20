---
description: "Team review — multi-avatar anti-pattern scan and principle alignment check on code, designs, or plans"
---

# Team Review

Review work through multiple expert lenses. Each avatar applies its own anti-patterns and principles.

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/marketplaces/*/plugins/dream-team/avatars/*/AVATAR.md`
- Glob `plugins/dream-team/avatars/*/AVATAR.md (within the plugin)`
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Identify the Artifact

Parse `$ARGUMENTS` for a file path, PR reference, or description of what to review. If nothing specified, ask via AskUserQuestion.

## Step 3: Select Team

Use AskUserQuestion to let the user choose:

- **"Auto-select (Recommended)"** — orchestrator maps the artifact's domain to relevant avatars. Propose 2-4 reviewers.
- **"Let me pick"** — present all avatars with `multiSelect: true`.
- **"Everyone"** — all avatars review. Maximum coverage.

## Step 4: Run Review

For each selected avatar:
1. Read its `AVATAR.md` and `references/anti-patterns.md`
2. Read the artifact being reviewed
3. Apply that avatar's anti-pattern checklist
4. Check principle alignment from that avatar's perspective
5. Present findings under a header with the avatar's name:

```
## {Avatar Name}'s Review
**Anti-patterns detected:**
- {anti-pattern}: {where} — {correction}

**Principle alignment:**
- {principle}: {assessment}

**Verdict:** {SOLID | CONCERNS | RETHINK}
```

After all reviews, synthesize:
```
## Synthesis
Unanimous concerns: ...
Split opinions: ...
Recommended fixes (priority order): ...
```

## Step 5: Continue

Use AskUserQuestion:
- "Apply the fixes" — make changes to the artifact
- "Dig deeper on a specific finding" — expand one reviewer's feedback
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
