---
name: debate
description: "Agents argue opposing positions through structured rounds, with a judge synthesizing the strongest arguments."
primitives: [fan-out, critique, loop, fan-in]
best-fit:
  - Contentious decisions with strong trade-offs
  - High-stakes choices where being wrong is costly
  - Reducing hallucination and groupthink
  - When you need adversarial stress-testing of ideas
token-cost: very high (N agents × M rounds)
latency: high (multiple rounds of back-and-forth)
quality-profile: "Highest quality for decisions — catches blind spots, but expensive and slow"
---

# Debate / Adversarial Pattern

Multiple agents take positions on a question and engage in structured argumentation. They critique each other's reasoning, expose flaws, and refine their positions. A judge (or consensus mechanism) determines the final answer.

## Flow

```
User prompt
    │
    ▼
fan-out: each avatar states initial position
    │
    ▼
┌─── Round 1 ───────────────────────┐
│ Avatar A critiques Avatar B's pos  │
│ Avatar B critiques Avatar A's pos  │
│ (all pairs exchange critiques)     │
└────────────────────────────────────┘
    │
    ▼ loop (until convergence or max rounds)
┌─── Round N ───────────────────────┐
│ Avatars refine positions based on  │
│ critiques received                 │
└────────────────────────────────────┘
    │
    ▼
fan-in: judge synthesizes strongest arguments
    │
    ▼
Response (with reasoning trail)
```

## Steps

1. **fan-out (opening statements)** — Each avatar states their initial position on the question, grounded in their principles. They must take a clear stance.

2. **Checkpoint: Opening positions** — Use AskUserQuestion after presenting opening positions:
   - "Continue the debate" — proceed to critique rounds
   - "Steer the discussion toward {topic}" — focus the critique on a specific aspect
   - "Add {avatar name} to the debate" — bring in another perspective
   - "I've heard enough" — skip to judgment

3. **critique (rounds)** — For each round:
   - Each avatar receives the other avatars' positions
   - Each avatar critiques the others: identifies logical flaws, missing considerations, or principle violations
   - Each avatar refines their own position based on valid critiques received

4. **Checkpoint: After each round** — Use AskUserQuestion:
   - "Another round" — continue the debate
   - "I'm convinced by {avatar name}" — end debate with that position
   - "Steer toward {topic}" — refocus the next round
   - "Move to judgment" — skip remaining rounds

5. **loop** — Repeat critique rounds until:
   - `converged` — positions stop changing significantly
   - `max-rounds` — hard limit reached (default: 3)
   - User chose to end early via checkpoint

6. **fan-in (judgment)** — Orchestrator acts as judge:
   - Identifies the strongest arguments from each side
   - Notes which critiques were substantive vs. superficial
   - Produces a final recommendation with explicit reasoning trail

## Debate Template

```
## Opening Positions
### {Avatar A}: {position summary}
{reasoning grounded in principles}

### {Avatar B}: {position summary}
{reasoning grounded in principles}

## Round {N}
### {Avatar A} responds to {Avatar B}:
{critique + refined position}

## Judgment
**Strongest arguments for:** {position}
**Strongest arguments against:** {position}
**Decision:** {recommendation with reasoning}
**Confidence:** {high/medium/low}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `rounds` | 3 | Maximum debate rounds |
| `debate_mode` | `free` | `free` (all-vs-all), `structured` (assigned pro/con), `socratic` (one questioner) |
| `judge` | `orchestrator` | Who judges: `orchestrator`, `vote`, or a specific avatar |
| `show_rounds` | `true` | Show full debate transcript or just the judgment |

## Anti-Sycophancy Measures

To prevent premature agreement (a known failure mode):
- Avatars are instructed to **maintain their position** unless presented with a genuinely compelling counter-argument grounded in their principles
- The orchestrator flags rounds where all agents agree too quickly and prompts for deeper challenge
- Each avatar must cite which specific principle or evidence changed their mind if they shift position

## Escalation Signals

The adaptive router should consider switching TO this pattern when:
- Map-reduce reveals strong disagreement between avatars
- User's question involves irreversible decisions
- Stakes are explicitly high

Switch FROM this pattern when:
- Avatars converge immediately (debate not needed) → simplify to **map-reduce**
- Topic is factual, not opinion-based → switch to **voting**
