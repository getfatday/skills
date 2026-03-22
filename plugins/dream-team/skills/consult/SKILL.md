---
name: consult
description: >
  Team consultation — get expert perspectives from your avatar team on any
  question. Assembles a team, selects a conversation pattern (map-reduce,
  debate, reflection, etc.), and coordinates multi-avatar discussion with
  structured checkpoints. Use whenever the user wants expert perspectives,
  asks "what do you think about X?", "dream team", "consult", "get
  perspectives on", or wants to discuss a question with expert avatars.
allowed-tools:
  - Read
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
---

# Team Consult

Get expert guidance from your avatar team. The orchestrator selects the best
conversation pattern for your question, defaulting to map-reduce (parallel
perspectives).

## Step 1: Discover Avatars

Scan for all installed avatars:
- Glob `~/.claude/plugins/marketplaces/*/plugins/dream-team/avatars/*/AVATAR.md`
- Glob `plugins/dream-team/avatars/*/AVATAR.md` (within the plugin)
- Glob `.claude/avatars/*/AVATAR.md` (project-level)

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Select Team

Use AskUserQuestion to let the user choose a selection mode:

**Options:**
- **"Auto-select (Recommended)"** — orchestrator analyzes the question, maps
  to domains, proposes the most relevant 2-4 avatars. User confirms.
- **"Let me pick"** — present all available avatars with `multiSelect: true`.
  User chooses.
- **"Everyone"** — include all installed avatars. Full panel.

If auto-select: match the user's question against each avatar's `domains[]`.
Rank by relevance. Propose top 2-4. Present via AskUserQuestion for confirmation.

## Step 3: Select Pattern

Read `patterns/router.md` and classify the user's question. The `pattern-hint`
for this command is `map-reduce`, but the adaptive router may override based on:
- Single-domain question → **moe-routing** (faster, one expert)
- Contentious topic detected → **debate** (adversarial stress-testing)
- Simple factual question → **voting** (consensus)

Announce the selected pattern to the user.

## Step 4: Run Consultation

Execute the selected pattern by reading its definition from
`patterns/{pattern-name}.md` and following its flow.

For each selected avatar:
1. Read its `AVATAR.md` fully (principles, voice, anti-patterns, vocabulary)
2. Execute the pattern's steps using the avatar team

The orchestrator monitors for mid-conversation signals and may switch patterns
(see `patterns/router.md` Phase 3).

## Step 5: Continue

Use AskUserQuestion:
- "Dig deeper with one of these experts" — transition to 1:1 (moe-routing)
- "Debate this point" — switch to debate pattern on a specific disagreement
- "Get a different team's take" — re-run selection
- "I'm good" — end
