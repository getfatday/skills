---
description: "Monarch Money overview — show accounts, balances, and net worth"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Monarch — Account Overview

Load the monarch agent and skill, then run the **accounts** task.

## Setup

1. Read the agent: `plugins/monarch/agents/monarch-agent.md` (relative to the getfatday-skills root, or find via Glob for `monarch-agent.md`)
2. Read the skill: `plugins/monarch/skills/personal-finance/SKILL.md`

## Execute

Run the **accounts** task as defined in the agent's task dispatch section.

Show:
- Net worth summary (assets, liabilities, net)
- Accounts table grouped by type (checking, savings, investment, credit card, loan, etc.)
- Flag any accounts with notable conditions (low balance, high credit utilization)

## Continuation

After presenting the overview, offer next steps via AskUserQuestion:

- "View recent transactions" -> run the transactions task (limit 25, no filters)
- "Check budget status" -> run the budget task
- "See cash flow trends" -> run the cashflow task
- "I'm good" -> end
