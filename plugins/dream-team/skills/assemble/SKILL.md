---
name: assemble
description: "Internal: form a multi-avatar team and coordinate via conversation patterns. Used by team:consult, team:review, team:plan, team:coach commands."
user-invocable: false
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
  - TeamCreate
  - SendMessage
---

Trigger: `/assemble` or "help me with X" or "I need engineering and product review"

You are a skill that assembles a team of avatar experts and coordinates them using conversation patterns.

## Steps

1. **Understand the request.** Identify the domains and expertise areas needed.

2. **Discover all available avatars** by scanning these locations:
   - `~/.claude/plugins/marketplaces/*/plugins/dream-team/avatars/*/AVATAR.md` (installed shared avatars)
   - `plugins/dream-team/avatars/*/AVATAR.md` (plugin avatars)
   - `.claude/avatars/*/AVATAR.md` (project-level avatars)

   Use Glob to find all AVATAR.md files. Read the `name`, `description`, and `domains` fields from each.

3. **Match avatars** to the user's request by comparing their `domains[]` against the expertise areas needed. Select the most relevant avatars.

4. **Propose the team** to the user via AskUserQuestion. Present a table:

   ```
   | Avatar | Domains | Role in Discussion |
   |--------|---------|--------------------|
   | {name} | {domains} | {why this avatar is relevant} |
   ```

   Ask the user to confirm or adjust the team.

5. **Select conversation pattern.** Read `patterns/router.md` and classify the task. If the invoking command has a `pattern-hint`, use it as the starting point. Present the selected pattern to the user.

   Available patterns (defined in `plugins/dream-team/patterns/`):
   - `map-reduce` — parallel perspectives, then synthesize
   - `sequential` — assembly line, each builds on previous
   - `supervisor` — decompose and delegate to specialists
   - `hierarchical` — recursive decomposition tree
   - `debate` — structured argumentation rounds
   - `blackboard` — shared workspace, agents self-activate
   - `voting` — independent answers, tally votes
   - `reflection` — generate-critique-refine loop
   - `moe-routing` — dispatch to single best specialist
   - `round-robin` — turn-based shared discussion

6. **Create the team** using TeamCreate. For each selected avatar:
   - Create a teammate agent that loads the avatar's AVATAR.md as its persona context
   - Each teammate should respond in character according to its persona

7. **Launch the orchestrator** agent (defined in `agents/orchestrator.md`) as the team lead. Pass it:
   - The selected pattern name
   - The user's question/task
   - The team roster

   The orchestrator reads the pattern definition and executes its flow, coordinating between teammates via SendMessage and monitoring for mid-conversation signals that suggest switching patterns.

8. When the discussion reaches a conclusion or the user is satisfied, summarize the key findings and end the session.
