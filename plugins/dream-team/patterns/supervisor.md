---
name: supervisor
description: "Central planner decomposes a task and delegates sub-tasks to specialist agents, then synthesizes results."
primitives: [route, chain, fan-in]
best-fit:
  - Complex tasks needing decomposition
  - When different sub-tasks need different specialists
  - Project planning and execution
  - Tasks where the orchestrator adds value through planning
token-cost: medium (selective routing, not all agents)
latency: medium (parallel sub-tasks possible)
quality-profile: "Strategic decomposition with targeted expertise — better than map-reduce when task is decomposable"
---

# Supervisor Pattern

The orchestrator acts as a project manager: analyzes the task, creates a plan, assigns sub-tasks to the most relevant specialists, collects results, and synthesizes.

## Flow

```
User prompt
    │
    ▼
Orchestrator (plan & decompose)
    │
    ├──► route → Avatar A (sub-task 1)
    ├──► route → Avatar B (sub-task 2)
    └──► route → Avatar C (sub-task 3)
    │
    ▼
fan-in (orchestrator synthesizes)
    │
    ▼
Response
```

## Steps

1. **Decompose** — Orchestrator analyzes the prompt and breaks it into discrete sub-tasks. Each sub-task is scoped to a single concern.

2. **route** — For each sub-task, select the best-fit avatar based on domain overlap. An avatar may receive multiple sub-tasks if they're in its domain.

3. **Delegate** — Send each sub-task to its assigned avatar via `SendMessage`. Sub-tasks that are independent can run in parallel; dependent ones run sequentially.

4. **fan-in** — Orchestrator collects all sub-task results and synthesizes:
   - Verify sub-task results are consistent with each other
   - Resolve any conflicts between specialists
   - Assemble into a coherent response

## Decomposition Template

```
## Task Decomposition
| Sub-task | Assigned To | Dependency | Status |
|----------|------------|------------|--------|
| {description} | {avatar} | {none/depends on #N} | pending |
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `decomposition` | `auto` | How to break down: `auto`, `by-domain`, `by-phase` |
| `parallel` | `true` | Run independent sub-tasks in parallel |
| `verify` | `true` | Cross-check sub-task results for consistency |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Sub-tasks are not independent (high coupling) → switch to **sequential**
- Specialists disagree on overlapping areas → escalate to **debate**
- Task is too simple for decomposition → narrow to **moe-routing**
