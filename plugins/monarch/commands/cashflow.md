---
description: "Monarch Money cash flow — income vs expenses, savings rate, monthly trends"
argument-hint: "[--start YYYY-MM-DD] [--end YYYY-MM-DD] [--months N]"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Monarch — Cash Flow

Load the monarch agent and skill, then run the **cashflow** task.

## Setup

1. Read the agent: `plugins/monarch/agents/monarch-agent.md`
2. Read the skill: `plugins/monarch/skills/personal-finance/SKILL.md`

## Argument Parsing

| Parameter | CLI Flag | Default |
|-----------|----------|---------|
| Start date | `--start-date YYYY-MM-DD` | none (uses CLI default) |
| End date | `--end-date YYYY-MM-DD` | none (uses CLI default) |
| Months back | `--months N` | 6 |

## Execute

Run the **cashflow** task as defined in the agent's task dispatch section.

Show:
- Current period: total income, total expenses, net cash flow
- Savings rate as a percentage
- Monthly trend table for the last N months
- Direction indicator: improving, stable, or declining
- Flag any months with unusual income or expense spikes

## Continuation

After presenting cash flow, offer via AskUserQuestion:

- "Drill into a specific month" -> ask which month, run transactions filtered to that month
- "See recurring expenses" -> run `gfd-monarch recurring list --format json` and present
- "Check budget" -> run the budget task
- "I'm good" -> end
