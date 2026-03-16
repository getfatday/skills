---
description: "Check Monarch Money connection health — auth status and account connectivity"
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Monarch — Status

Load the monarch agent and skill, then run the **status** task.

## Setup

1. Read the agent: `plugins/monarch/agents/monarch-agent.md`

## Execute

Run the **status** task as defined in the agent's task dispatch section.

Show:
- Authentication status (authenticated or not)
- Number of connected accounts
- List of accounts with their connection status if available
- Any errors encountered

If auth has expired, tell the user to run `gfd-monarch auth login` and stop.

## Continuation

If status is healthy, offer via AskUserQuestion:

- "Show account overview" -> run the accounts task
- "I'm good" -> end

If status is unhealthy, just report the issue and suggest remediation. Don't offer further data commands.
