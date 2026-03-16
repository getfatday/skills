---
name: imdb:top
description: IMDB top lists — Top 250 movies, Top 250 shows, current box office
argument-hint: [movies|shows|box-office]
allowed-tools:
  - Bash
  - Read
---

<objective>
Fetch IMDB top lists. Defaults to top movies if no subcommand given.
</objective>

<context>
Arguments: $ARGUMENTS

Parse:
- "movies" or empty: Top 250 movies
- "shows" or "tv": Top 250 TV shows
- "box-office": Current box office rankings
</context>

<workflow>
Dispatch to imdb-agent with the list type.
</workflow>

<agent_dispatch>
@agents/imdb-agent.md
</agent_dispatch>
