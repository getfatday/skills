---
description: "Search or list Copilot Money transactions — supports date range, category, amount, account filters"
argument-hint: "[search text] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--category Name] [--account Name] [--min N] [--max N]"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Copilot Money — Transactions

Load the copilot-money agent and skill, then run the **transactions** task.

## Setup

1. Read the agent: `plugins/copilot-money/agents/copilot-money-agent.md`
2. Read the skill: `plugins/copilot-money/skills/personal-finance/SKILL.md`

## Argument Parsing

Parse the user's input for these optional parameters:

| Parameter | CLI Flag | Default |
|-----------|----------|---------|
| Start date | `--start YYYY-MM-DD` | none |
| End date | `--end YYYY-MM-DD` | none |
| Category | `--category "Name"` | none |
| Account | `--account "Name"` | none |
| Min amount | `--min N` | none |
| Max amount | `--max N` | none |
| Exclude transfers | `--exclude-transfers` | false |

If the user provides natural language dates (e.g., "last week", "this month"), convert them to YYYY-MM-DD format based on today's date.

If the user provides natural language like "restaurant spending" or "transactions over $100", map to the appropriate flags (`--category "Restaurant"`, `--min 100`).

If no arguments are provided, list all cached transactions (no filters).

## Execute

Run the **transactions** task as defined in the agent's task dispatch section, passing the parsed parameters.

## Continuation

After presenting results, offer via AskUserQuestion:

- "Narrow this search" -> ask for additional filters, re-run
- "Show more detail" -> re-run with different filters
- "Back to overview" -> run the accounts task
- "I'm good" -> end
