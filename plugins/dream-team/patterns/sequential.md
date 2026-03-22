---
name: sequential
description: "Chain agents in a pipeline where each agent's output feeds the next, building incrementally."
primitives: [chain]
best-fit:
  - Multi-step refinement (draft → review → polish)
  - Tasks with natural stage ordering
  - When later agents need earlier agents' context
  - Staged review or approval workflows
token-cost: medium (sequential, but context grows)
latency: high (fully sequential)
quality-profile: "Deep, iterative refinement — each stage builds on the last"
---

# Sequential Pipeline Pattern

Agents process in order, like an assembly line. Each agent receives the original prompt plus all previous agents' outputs, adding their specialized transformation.

## Flow

```
User prompt
    │
    ▼
Avatar A (e.g., architect)
    │ output A
    ▼
Avatar B (e.g., implementer) ← receives prompt + output A
    │ output B
    ▼
Avatar C (e.g., reviewer) ← receives prompt + output A + output B
    │ output C
    ▼
Final response (output C, or orchestrator summary)
```

## Steps

1. **Determine order** — Orchestrator sequences avatars by their role in the pipeline. Common orderings:
   - Strategic → Tactical → Operational
   - Design → Implement → Test → Document
   - Broad → Narrow → Critique

2. **chain** — For each avatar in sequence:
   - Send the original prompt + accumulated context from prior stages
   - Avatar responds in its voice, building on previous work
   - Output is appended to the running context

3. **Present** — Final output is the last avatar's response, optionally with an orchestrator summary of how the work evolved through stages.

## Stage Template

```
## Stage {N}: {Avatar Name}
**Building on:** {summary of prior stages}
**Contribution:** {this avatar's addition/refinement}
**Handoff to next:** {what the next stage should focus on}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `order` | `auto` | Agent ordering: `auto` (orchestrator decides), or explicit list |
| `context_mode` | `accumulate` | `accumulate` (full history) or `summary` (compressed handoff) |
| `show_stages` | `true` | Show each stage's output or just the final result |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- A stage produces output that invalidates earlier stages → inject **reflection** loop
- Task is embarrassingly parallel (no dependencies) → switch to **map-reduce**
- Pipeline stalls at a stage → switch to **moe-routing** for a different specialist
