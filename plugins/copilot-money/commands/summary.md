---
description: "Copilot Money financial summary — income vs expenses, savings rate, top categories"
argument-hint: "[--period YYYY-MM] [--start YYYY-MM-DD] [--end YYYY-MM-DD]"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Copilot Money — Financial Summary

Load the copilot-money agent and skill, then run the **summary** task.

## Setup

1. Read the agent: `plugins/copilot-money/agents/copilot-money-agent.md`
2. Read the skill: `plugins/copilot-money/skills/personal-finance/SKILL.md`

## Argument Parsing

| Parameter | CLI Flag | Default |
|-----------|----------|---------|
| Period | `--period YYYY-MM` | none (all cached data) |
| Start date | `--start YYYY-MM-DD` | none |
| End date | `--end YYYY-MM-DD` | none |

If the user says "this month" or "last month", convert to the appropriate --period value.

## Execute

Run the **summary** task as defined in the agent's task dispatch section.

Show:
- Net worth
- Total income, total expenses, net cash flow
- Savings rate as a percentage
- Top spending categories with amounts
- Flag any unusual patterns or notable items

## Continuation

After presenting the summary, offer via AskUserQuestion:

- "Drill into a specific category" -> ask which category, run transactions filtered to it
- "See recurring expenses" -> run `gfd-copilot-money recurring --format json` and present
- "Check budget" -> run the budget task
- "I'm good" -> end
