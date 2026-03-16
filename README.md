# getfatday/skills

Claude Code plugins for personal finance and entertainment data. Install a plugin and use slash commands to query your Monarch Money accounts or search IMDB, all inside Claude Code.

## Install

Add the marketplace, then install whichever plugins you want:

```bash
claude plugin marketplace add getfatday/skills
claude plugin install monarch
claude plugin install imdb
```

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
