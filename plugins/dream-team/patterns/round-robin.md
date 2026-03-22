---
name: round-robin
description: "Agents take turns in a shared conversation, each seeing and building on all previous contributions."
primitives: [chain, fan-in, loop]
best-fit:
  - Brainstorming and ideation
  - Planning sessions needing progressive refinement
  - When agents should build on each other's ideas
  - Creative problem-solving
token-cost: very high (context grows N × M per round)
latency: high (sequential within rounds, multiple rounds)
quality-profile: "Richest cross-pollination — agents genuinely build on each other, but expensive and prone to groupthink"
---

# Round-Robin / Group Chat Pattern

Agents take turns speaking in a shared conversation. Each agent sees the full history and contributes when called. The orchestrator manages turn order, either fixed rotation or dynamic selection.

## Flow

```
User prompt
    │
    ▼
┌─── Round 1 ────────────────────────┐
│ Avatar A speaks (sees: prompt)      │
│ Avatar B speaks (sees: prompt + A)  │
│ Avatar C speaks (sees: prompt+A+B)  │
└─────────────────────────────────────┘
    │
    ▼ loop (additional rounds if needed)
┌─── Round 2 ────────────────────────┐
│ Avatar B responds to C's point     │
│ Avatar A builds on B's revision    │
│ Avatar C synthesizes              │
└─────────────────────────────────────┘
    │
    ▼
fan-in: orchestrator summarizes discussion
    │
    ▼
Response
```

## Steps

1. **Set turn order** — Orchestrator determines speaking order:
   - `fixed` — rotate through avatars in a set order
   - `dynamic` — orchestrator selects the next speaker based on who has the most relevant thing to add
   - `raise-hand` — each avatar is asked if they want to respond; most eager goes next

2. **chain (per turn)** — Each avatar receives the full conversation history and contributes:
   - New ideas building on previous speakers
   - Challenges to previous points (with reasoning)
   - Synthesis of emerging themes
   - Questions directed at specific other avatars

3. **loop** — Continue rounds until:
   - Discussion has converged on a direction
   - Maximum rounds reached
   - Orchestrator judges sufficient coverage

4. **fan-in** — Orchestrator summarizes:
   - Key ideas that emerged
   - Evolution of thinking through the discussion
   - Final recommendations

## Turn Template

```
## Round {N}

### {Avatar Name} (Turn {M}):
{Response building on conversation so far}
**Key point:** {one-sentence summary}
**Directed at:** {specific avatar, or "all"}
```

## Context Management

To prevent context window explosion:
- After each round, orchestrator produces a **round summary** (compressed)
- Next round receives: original prompt + round summaries + current round's full text
- This keeps context growth linear rather than quadratic

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `rounds` | 2 | Maximum discussion rounds |
| `turn_order` | `dynamic` | `fixed`, `dynamic`, or `raise-hand` |
| `context_mode` | `summarized` | `full` (everything) or `summarized` (compressed between rounds) |
| `show_rounds` | `true` | Show full discussion or just the synthesis |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Agents are repeating each other (groupthink) → inject **debate** for adversarial tension
- One agent dominates the conversation → narrow to **moe-routing** or rebalance
- Discussion is diverging without progress → impose structure with **supervisor**
