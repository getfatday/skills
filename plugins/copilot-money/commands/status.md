---
description: "Check Copilot Money cache health — cache path, size, and record counts"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Copilot Money — Status

Load the copilot-money agent and skill, then run the **status** task.

## Setup

1. Read the agent: `plugins/copilot-money/agents/copilot-money-agent.md`

## Execute

Run the **status** task as defined in the agent's task dispatch section.

Show:
- Cache path and file size
- Total document count
- Per-collection counts (accounts, transactions, categories, budgets, recurring)
- Any errors encountered

If the cache is not found, tell the user: "Copilot Money cache not found. Open the Copilot Money app and sync your accounts."

## Continuation

If status is healthy, offer via AskUserQuestion:

- "Show account overview" -> run the accounts task
- "I'm good" -> end

If status is unhealthy, just report the issue and suggest remediation. Don't offer further data commands.
