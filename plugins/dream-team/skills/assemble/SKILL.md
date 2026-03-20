---
name: assemble
description: "Internal: form a multi-avatar team. Used by team:consult, team:review, team:plan, team:coach commands."
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

You are a skill that assembles a team of avatar experts to address the user's request.

## Steps

1. Understand the user's request. Identify the domains and expertise areas needed.

2. Discover all available avatars by scanning these three locations:
   - `~/.claude/plugins/avatar-*/AVATAR.md` (installed shared avatars)
   - `.claude/avatars/*/AVATAR.md` (project-level avatars)
   - `~/.claude/plugins/*/avatars/*/AVATAR.md` (legacy layout)

   Use Glob to find all AVATAR.md files. Read the `name`, `description`, and `domains` fields from each.

3. Match avatars to the user's request by comparing their `domains[]` against the expertise areas needed. Select the most relevant avatars.

4. Propose the team to the user via AskUserQuestion. Present a table:

   ```
   | Avatar | Domains | Role in Discussion |
   |--------|---------|--------------------|
   | {name} | {domains} | {why this avatar is relevant} |
   ```

   Ask the user to confirm or adjust the team.

5. On confirmation, create the team using TeamCreate. For each selected avatar:
   - Create a teammate agent that loads the avatar's AVATAR.md as its persona context
   - Each teammate should respond in character according to its persona

6. Launch the orchestrator agent (defined in `agents/orchestrator.md`) as the team lead to coordinate the discussion. The orchestrator:
   - Poses the user's question to each avatar teammate
   - Ensures each avatar responds in character
   - Synthesizes responses into actionable recommendations
   - Uses SendMessage to coordinate between teammates
   - Uses AskUserQuestion to check in with the user

7. When the discussion reaches a conclusion or the user is satisfied, summarize the key findings and end the session.
