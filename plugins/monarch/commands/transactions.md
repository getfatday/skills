---
description: "Search or list Monarch Money transactions — supports date range, category, text filters"
argument-hint: "[search text] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--category Name] [--account Name] [--limit N]"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Monarch — Transactions

Load the monarch agent and skill, then run the **transactions** task.

## Setup

1. Read the agent: `plugins/monarch/agents/monarch-agent.md`
2. Read the skill: `plugins/monarch/skills/personal-finance/SKILL.md`

## Argument Parsing

Parse the user's input for these optional parameters:

| Parameter | CLI Flag | Default |
|-----------|----------|---------|
| Free text search | `--search "text"` | none |
| Start date | `--start-date YYYY-MM-DD` | none |
| End date | `--end-date YYYY-MM-DD` | none |
| Category | `--category "Name"` | none |
| Account | `--account "Name"` | none |
| Limit | `--limit N` | 25 |

If the user provides natural language dates (e.g., "last week", "this month"), convert them to YYYY-MM-DD format based on today's date.

If no arguments are provided, list the 25 most recent transactions.

## Execute

Run the **transactions** task as defined in the agent's task dispatch section, passing the parsed parameters.

## Continuation

After presenting results, offer via AskUserQuestion:

- "Narrow this search" -> ask for additional filters, re-run
- "Show more results" -> increase limit or offset, re-run
- "Back to overview" -> run the accounts task
- "I'm good" -> end
