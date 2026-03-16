---
name: imdb:person
description: Get person details — bio, filmography
argument-hint: <id or name> [--filmography]
allowed-tools:
  - Bash
  - Read
---

<objective>
Fetch information about a person (actor, director, writer). If given a name instead of ID, search first.
</objective>

<context>
Arguments: $ARGUMENTS

Parse:
- First arg: person ID or name to search
- --filmography flag: include full filmography
</context>

<workflow>
1. If arg is an ID, fetch person info directly
2. If arg is a name, search first, then fetch the top result
3. If --filmography, also fetch filmography
4. Present combined results

Dispatch to imdb-agent.
</workflow>

<agent_dispatch>
@agents/imdb-agent.md
</agent_dispatch>
