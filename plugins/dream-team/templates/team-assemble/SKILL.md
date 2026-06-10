---
name: team-assemble
tier: 2-materialized
materialized: "2026-06-08"
description: "Internal: form a multi-team-member team and coordinate via conversation patterns. Used by the consult, review, plan, and coach commands."
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
targets: ["*"]
---

You are a skill that assembles a team of expert team-members and coordinates them using conversation patterns.

## Steps

1. **Understand the request.** Identify the domains and expertise areas needed.

2. **Discover the local roster** by scanning the consumer's blueprints:
   - Glob `.config/team/team-members/*.md` — every blueprint is a roster entry
   - Read the `name`, `description`, and `domains[]` fields from each
   - The corresponding persona skill is materialized at `.claude/skills/{slug}/SKILL.md`; rely on Claude Code's standard skill discovery to find it

3. **Match team-members** to the user's request by comparing their `domains[]` against the expertise areas needed. Select the most relevant team-members.

4. **Propose the team** to the user via AskUserQuestion. Present a table:

   ```
   | Team Member | Domains | Role in Discussion |
   |-------------|---------|--------------------|
   | {name} | {domains} | {why this team-member is relevant} |
   ```

   Ask the user to confirm or adjust the team.

5. **Select conversation pattern.** Read `patterns/router.md` (located in this skill's `patterns/` subdirectory) and classify the task. If the invoking command has a `pattern-hint`, use it as the starting point. Present the selected pattern to the user.

   Available patterns (defined in the colocated `patterns/` subdirectory):
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

6. **Create the team** using TeamCreate. For each selected team-member:
   - Create a teammate agent that loads the team-member's materialized skill (`.claude/skills/{slug}/SKILL.md`) as its persona context
   - Each teammate should respond in character according to its persona

7. **Launch the orchestrator** agent (defined at `.claude/agents/orchestrator.md`) as the team lead. Pass it:
   - The selected pattern name
   - The user's question/task
   - The team roster

   The orchestrator reads the pattern definition and executes its flow, coordinating between teammates via SendMessage and monitoring for mid-conversation signals that suggest switching patterns.

8. When the discussion reaches a conclusion or the user is satisfied, summarize the key findings and end the session.
