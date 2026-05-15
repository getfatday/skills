# imdb

IMDB movie and TV data — search titles, look up people, browse top lists, and pull box-office numbers.

## When to use

Ask Claude about movies, shows, or actors inside Claude Code:

- "Search IMDB for Dune"
- "Who's in the cast of Oppenheimer?"
- "What's Christopher Nolan's filmography?"
- "Show me this week's box office"
- "Top 250 movies of all time"

## Components

| Type | Name | Purpose |
|------|------|---------|
| Command | `/imdb` | Search IMDB for movies, shows, or people |
| Command | `/imdb:movie` | Detailed movie info — cast, box office, ratings |
| Command | `/imdb:person` | Person details — bio, filmography |
| Command | `/imdb:top` | Top lists — Top 250 movies, Top 250 shows, current box office |
| Agent | `imdb-agent` | Orchestrator that runs the CLI and presents results |
| Skill | `entertainment` | Domain knowledge — ratings context, box office benchmarks, genre conventions |

## Setup

Requires the `gfd-imdb` CLI (shipped in this repo at `clis/imdb-cli/`).

```bash
uv tool install --from ./clis/imdb-cli gfd-imdb-cli
```

No auth required — uses public IMDB data via Cinemagoer.
