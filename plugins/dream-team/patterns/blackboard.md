---
name: blackboard
description: "Agents share a workspace, reading and writing findings. Agents self-activate when they can contribute."
primitives: [share, monitor, route, fan-in]
best-fit:
  - Open-ended exploration and research
  - Problems where the solution path is unclear
  - When agents need to build on each other's partial results
  - Emergent, creative problem-solving
token-cost: variable (agents only activate when relevant)
latency: variable (depends on activation patterns)
quality-profile: "Emergent and creative — great for exploration, but less predictable than structured patterns"
---

# Blackboard / Shared Workspace Pattern

All agents share a common workspace where they read and write findings. The orchestrator monitors the workspace and activates whichever agent is best positioned to contribute next. Agents build on each other's partial results incrementally.

## Flow

```
User prompt → Orchestrator seeds blackboard
    │
    ▼
┌─── Blackboard (shared state) ──────────┐
│ key: "problem"  → user's question       │
│ key: "finding-1" → Avatar A's insight   │
│ key: "finding-2" → Avatar C's addition  │
│ key: "question-1" → Avatar B's gap      │
│ ...                                     │
└─────────────────────────────────────────┘
    │         ▲         ▲         ▲
    ▼         │         │         │
monitor → activate most relevant agent
    │
    ▼
Agent reads blackboard → writes new finding
    │
    ▼ loop (until done or max iterations)
fan-in: orchestrator summarizes blackboard
    │
    ▼
Response
```

## Steps

1. **Seed** — Orchestrator writes the user's prompt and any initial context to the blackboard.

2. **monitor + route** — Orchestrator evaluates each available avatar:
   - What's currently on the blackboard?
   - Which avatar's domains are most relevant to the current state?
   - Which avatar can fill the biggest gap in current findings?
   - Activate that avatar.

3. **share** — Activated avatar reads the blackboard, then writes:
   - New findings or insights
   - Questions that need answering
   - Connections between existing findings
   - Challenges to existing findings

4. **loop** — Repeat monitor → activate → share until:
   - `converged` — no agent has new information to add
   - `max-iterations` — hard limit reached (default: 10 activations)
   - Orchestrator judges the blackboard has sufficient coverage

5. **fan-in** — Orchestrator reads the final blackboard state and synthesizes a response, tracing how findings built on each other.

## Blackboard Schema

```
{
  "problem": "the original question",
  "findings": [
    { "author": "avatar-name", "type": "insight|question|challenge|connection", "content": "...", "references": ["finding-id"] }
  ],
  "status": "exploring|converging|complete"
}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `max_activations` | 10 | Maximum agent activations before forced synthesis |
| `activation_strategy` | `most-relevant` | `most-relevant`, `least-heard`, `round-robin` |
| `allow_challenges` | `true` | Agents can challenge each other's findings |

## Escalation Signals

The adaptive router should consider switching TO this pattern when:
- Problem is poorly defined and needs exploration
- Sequential approaches keep hitting dead ends
- Multiple domains intersect in unpredictable ways

Switch FROM this pattern when:
- Blackboard converges quickly → simplify to **map-reduce**
- One clear direction emerges → narrow to **sequential** or **moe-routing**
- Agents are going in circles → impose structure with **supervisor**
