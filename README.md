# getfatday/skills

Personal Claude Code plugins and the standalone CLIs they wrap. Plugins live under `plugins/`, CLIs under `clis/`. Works with Claude Code; CLIs work standalone in any terminal.

## Install

### Claude Code (CLI or VS Code)

```bash
claude plugin marketplace add getfatday/skills
claude plugin install copilot-money
claude plugin install imdb
claude plugin install dream-team
claude plugin install document
```

### Standalone CLIs

The Python CLIs are usable outside Claude Code. Install with uv:

```bash
uv tool install --from ./clis/copilot-money-cli gfd-copilot-money-cli
uv tool install --from ./clis/imdb-cli gfd-imdb-cli
```

All CLIs support `--format json` for machine-readable output (see `CLAUDE.md` for conventions).

## Plugins

| Plugin | What it does |
|--------|--------------|
| [copilot-money](plugins/copilot-money/README.md) | Personal finance — accounts, transactions, budgets, summaries from the local Copilot Money cache |
| [document](plugins/document/README.md) | Document type system — define types, generate per-type management skills |
| [dream-team](plugins/dream-team/README.md) | Avatar framework and marketplace — create, install, recruit, and orchestrate AI expert agents |
| [imdb](plugins/imdb/README.md) | IMDB movie and TV data — search, details, cast, box office, top lists |

## CLIs

| CLI | Command | Purpose |
|-----|---------|---------|
| copilot-money-cli | `gfd-copilot-money` | Reads local Copilot Money cache (LevelDB/Firestore) |
| imdb-cli | `gfd-imdb` | IMDB data via Cinemagoer |

## Contributing

See [CLAUDE.md](CLAUDE.md) for repo structure, conventions, and development commands (`make lint`, `make test`, `make typecheck`).
