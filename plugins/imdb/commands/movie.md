---
name: imdb:movie
description: Get detailed movie information — cast, box office, ratings
argument-hint: <id or title> [--cast] [--box-office]
allowed-tools:
  - Bash
  - Read
---

<objective>
Fetch detailed information about a specific movie. If given a title instead of ID, search first.
</objective>

<context>
Arguments: $ARGUMENTS

Parse:
- First arg: movie ID (numeric/tt-prefixed) or title to search
- --cast flag: include full cast
- --box-office flag: include box office data
</context>

<workflow>
1. If arg is an ID, fetch movie info directly
2. If arg is a title, search first, then fetch the top result
3. If --cast, also fetch cast
4. If --box-office, also fetch box office data
5. Present combined results

Dispatch to imdb-agent.
</workflow>

<agent_dispatch>
@agents/imdb-agent.md
</agent_dispatch>
