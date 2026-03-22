---
name: hierarchical
description: "Recursive tree delegation — agents decompose and spawn sub-agents, building a dynamic task tree."
primitives: [recurse, route, chain, fan-in]
best-fit:
  - Very complex, deeply nested problems
  - Tasks requiring multi-level decomposition
  - Research requiring depth-first exploration
  - When sub-problems are themselves complex
token-cost: high (recursive agent spawning)
latency: high (tree depth × processing)
quality-profile: "Handles arbitrary complexity through recursive specialization — risk of context loss at depth"
---

# Hierarchical Delegation Pattern

Extends the supervisor pattern into a recursive tree. The root agent decomposes the task, spawns sub-agents, and each sub-agent may further decompose and spawn their own sub-agents. Leaf agents perform atomic work; results propagate back up.

## Flow

```
User prompt
    │
    ▼
Root Agent (decompose)
    ├──► Agent A (sub-task 1)
    │       ├──► Agent A1 (sub-sub-task)
    │       └──► Agent A2 (sub-sub-task)
    ├──► Agent B (sub-task 2)
    └──► Agent C (sub-task 3)
            └──► Agent C1 (sub-sub-task)
    │
    ▼ (results propagate up)
Root Agent (synthesize)
    │
    ▼
Response
```

## Steps

1. **Decompose** — Root agent breaks the task into sub-tasks.

2. **recurse** — For each sub-task:
   - **route** to the best-fit avatar
   - Avatar assesses if the sub-task needs further decomposition
   - If yes: avatar decomposes and spawns sub-agents (recursive)
   - If no: avatar processes the atomic task directly

3. **Propagate** — Leaf agents return results to their parent. Each parent agent synthesizes its children's results and returns to its own parent.

4. **fan-in** — Root agent receives all synthesized sub-results and produces the final response.

## Safety Limits

| Limit | Default | Description |
|-------|---------|-------------|
| `max_depth` | 3 | Maximum tree depth before forcing leaf execution |
| `max_agents` | 10 | Maximum total agents spawned across all levels |
| `timeout` | 5 min | Maximum wall-clock time for entire tree |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `decomposition` | `auto` | How to break down at each level |
| `summary_at_depth` | `true` | Compress context at each level to manage token budget |
| `parallel_siblings` | `true` | Run sibling sub-tasks in parallel |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Task is shallow (doesn't need recursion) → drop to **supervisor**
- Tree is becoming too deep with diminishing returns → cap depth and switch to **map-reduce**
- Context loss at depth is degrading quality → switch to **blackboard** for shared state
