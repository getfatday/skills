---
tier: 2-materialized
materialized: "2026-06-08"
description: "Team consultation — get expert perspectives from your team on any question"
pattern-hint: map-reduce
---

# Team Consult

Get expert guidance from your team. The orchestrator selects the best conversation pattern for your question, defaulting to map-reduce (parallel perspectives).

## Step 1: Discover Team Members

Scan the consumer's local roster — `.config/team/team-members/*.md`. Each blueprint declares a roster entry; the matching materialized persona lives at `.claude/skills/{slug}/SKILL.md`.

For each, read the `name`, `description`, and `domains[]` fields.

## Step 2: Select Team

Use AskUserQuestion to let the user choose a selection mode:

**Options:**
- **"Auto-select (Recommended)"** — orchestrator analyzes the question, maps to domains, proposes the most relevant 2-4 team-members. User confirms.
- **"Let me pick"** — present all available team-members with `multiSelect: true`. User chooses.
- **"Everyone"** — include all installed team-members. Full panel.

If auto-select: match `$ARGUMENTS` against each team-member's `domains[]`. Rank by relevance. Propose top 2-4. Present via AskUserQuestion for confirmation.

## Step 3: Select Pattern

Read `.claude/skills/team-assemble/patterns/router.md` and classify the user's question. The `pattern-hint` for this command is `map-reduce`, but the adaptive router may override based on:
- Single-domain question → **moe-routing** (faster, one expert)
- Contentious topic detected → **debate** (adversarial stress-testing)
- Simple factual question → **voting** (consensus)

Announce the selected pattern to the user.

## Step 4: Run Consultation

Execute the selected pattern by reading its definition from `.claude/skills/team-assemble/patterns/{pattern-name}.md` and following its flow.

For each selected team-member:
1. Read its materialized persona at `.claude/skills/{slug}/SKILL.md` (principles, voice, anti-patterns, vocabulary)
2. Execute the pattern's steps using the assembled team

The orchestrator monitors for mid-conversation signals and may switch patterns (see `.claude/skills/team-assemble/patterns/router.md` Phase 3).

## Step 5: Continue

Use AskUserQuestion:
- "Dig deeper with one of these experts" — transition to 1:1 (moe-routing)
- "Debate this point" — switch to debate pattern on a specific disagreement
- "Get a different team's take" — re-run selection
- "I'm good" — end


ARGUMENTS: $ARGUMENTS
