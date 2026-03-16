# getfatday/skills

Plugins for personal finance and entertainment data. Install a plugin and use slash commands to query your Monarch Money accounts or search IMDB. Works with Claude Code, Cursor, and any tool that reads the `claude` CLI.

## Install

### Claude Code (CLI or VS Code)

```bash
claude plugin marketplace add getfatday/skills
claude plugin install monarch
claude plugin install imdb
```

### Cursor

Cursor auto-discovers skills from `.claude/skills/` directories. After installing a plugin with the `claude` CLI (above), Cursor's Agent picks up the skill knowledge automatically. Slash commands (`/monarch`, `/imdb`) are Claude Code specific, but the domain skills (personal-finance, entertainment) work in Cursor's Agent context.

### Any tool with a terminal

The CLIs work standalone. Install them with uv and call `gfd-monarch` or `gfd-imdb` from any terminal, script, or agent that can run shell commands.

## Plugins

| Plugin | Commands | What it does |
|--------|----------|--------------|
| **monarch** | `/monarch`, `/monarch:transactions`, `/monarch:budget`, `/monarch:cashflow`, `/monarch:status` | Query Monarch Money accounts, transactions, budgets, and cash flow |
| **imdb** | `/imdb`, `/imdb:movie`, `/imdb:person`, `/imdb:top` | Search IMDB for movies, people, box office, and top lists |

### Usage

Ask Claude about your finances:
```
/monarch          → Account overview with net worth and balances
/monarch:budget   → Current month budget vs actuals
```

Look up movies:
```
/imdb Oppenheimer       → Search and get movie details
/imdb:top               → Top 250 movies, shows, or current box office
```

## CLIs

Each plugin wraps a standalone CLI. You can use these directly outside Claude Code.

| CLI | Command | Subcommands |
|-----|---------|-------------|
| **monarch-cli** | `gfd-monarch` | `auth`, `accounts`, `transactions`, `categories`, `budgets`, `cashflow`, `recurring` |
| **imdb-cli** | `gfd-imdb` | `search`, `movie`, `person`, `top`, `upcoming` |

All CLIs support `--json` for machine-readable output and `--format` for table/csv/json where applicable.

Install from the repo with uv:
```bash
cd clis/monarch-cli && uv pip install -e .
cd clis/imdb-cli && uv pip install -e .
```

## Contributing

See [CLAUDE.md](CLAUDE.md) for repo structure, conventions, and development commands (`make lint`, `make test`, `make typecheck`).
