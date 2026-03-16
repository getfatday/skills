---
name: imdb
description: Search IMDB for movies, shows, and people
argument-hint: <query or movie title>
allowed-tools:
  - Bash
  - Read
---

<objective>
Entry point for IMDB queries. Searches movies by default. Accepts a title, person name, or IMDB ID.
</objective>

<context>
Arguments: $ARGUMENTS

Parse the input:
- If it looks like an IMDB ID (numeric or tt-prefixed): fetch movie info directly
- If it looks like a person name (no obvious movie title signals): search people
- Otherwise: search movies
</context>

<workflow>
Dispatch to the imdb-agent with the parsed intent and arguments.
</workflow>

<agent_dispatch>
@agents/imdb-agent.md
</agent_dispatch>
