# copilot-money

Personal finance data access for Copilot Money — read accounts, transactions, budgets, and spending summaries from the local Copilot Money cache. No API required.

## When to use

Use this plugin to ask Claude about your finances inside Claude Code:

- "What's my net worth?"
- "Show me transactions over $200 this month"
- "How am I tracking against budget?"
- "What did I spend on groceries in April?"

The plugin reads the LevelDB/Firestore cache that the Copilot Money desktop app maintains locally. Numbers are exactly what you see in the app.

## Components

| Type | Name | Purpose |
|------|------|---------|
| Command | `/copilot-money` | Accounts and balances overview |
| Command | `/copilot-money:transactions` | Search/list transactions with filters |
| Command | `/copilot-money:budget` | Current month budget vs actual |
| Command | `/copilot-money:summary` | Income vs expenses, savings rate, top categories |
| Command | `/copilot-money:status` | Cache health (path, size, record counts) |
| Agent | `copilot-money-agent` | Orchestrator that runs the CLI and parses output |
| Skill | `personal-finance` | Domain knowledge — net worth trends, cash flow, budget variance, savings benchmarks |

## Setup

Requires the `gfd-copilot-money` CLI (shipped in this repo at `clis/copilot-money-cli/`).

```bash
uv tool install --from ./clis/copilot-money-cli gfd-copilot-money-cli
```

The CLI auto-discovers the Copilot Money desktop app's cache directory. Run `/copilot-money:status` to verify the cache is found and readable.

## Privacy

All data stays local. The CLI reads the cache directly and never makes network calls. The agent is instructed to never write sensitive financial data to files.
