---
description: "Copilot Money budget overview — current month budget vs actual spending"
argument-hint: "[--month YYYY-MM]"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Copilot Money — Budget

Load the copilot-money agent and skill, then run the **budget** task.

## Setup

1. Read the agent: `plugins/copilot-money/agents/copilot-money-agent.md`
2. Read the skill: `plugins/copilot-money/skills/personal-finance/SKILL.md`

## Argument Parsing

| Parameter | CLI Flag | Default |
|-----------|----------|---------|
| Month | `--month YYYY-MM` | current month |

If the user says "last month", convert to the appropriate YYYY-MM.

## Execute

Run the **budget** task as defined in the agent's task dispatch section.

Show:
- Overall budget health: total budgeted vs total spent, % used
- Per-category breakdown: budgeted, actual, remaining, % used
- Flag over-budget categories clearly
- Calculate how much is left for the remainder of the month

## Continuation

After presenting the budget, offer via AskUserQuestion:

- "Show transactions for an over-budget category" -> ask which category, then run transactions filtered by that category and current month
- "Compare to last month" -> run budget for previous month
- "See financial summary" -> run the summary task
- "I'm good" -> end
