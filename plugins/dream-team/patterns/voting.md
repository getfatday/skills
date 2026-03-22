---
name: voting
description: "Agents independently answer, then a voting mechanism selects or synthesizes the best response."
primitives: [fan-out, vote]
best-fit:
  - Questions with a clear right answer
  - Quick consensus checks
  - When you want high confidence in correctness
  - Factual or technical questions
token-cost: high (N parallel calls, but no rounds)
latency: low (single parallel round)
quality-profile: "High confidence through independence — each agent is unbiased by others, but no cross-pollination"
---

# Voting / Ensemble Pattern

Each agent independently generates a candidate answer. No agent sees another's response. A voting mechanism determines the final answer — either majority vote, weighted vote, or a judge that reviews all candidates.

## Flow

```
User prompt
    │
    ├──► Avatar A ──► Answer A ──┐
    ├──► Avatar B ──► Answer B ──┤  fan-out (parallel, isolated)
    ├──► Avatar C ──► Answer C ──┤
    └──► Avatar D ──► Answer D ──┘
                                 │
                           vote (tally)
                                 │
                            Response
```

## Steps

1. **fan-out** — Send the prompt to all selected avatars in parallel. Each avatar responds independently with NO knowledge of others' answers.

2. **vote** — Apply the voting method:
   - **majority** — find the most common answer/direction
   - **weighted** — weight each avatar by domain relevance to the question
   - **ranked** — each avatar ranks options, aggregate via Borda count
   - **judge** — orchestrator reviews all candidates and selects the best

3. **Present** — Report the winning answer with confidence level based on agreement:
   - Unanimous → high confidence
   - Majority → medium confidence
   - Split → low confidence (consider escalating to debate)

## Voting Template

```
## Votes
| Avatar | Answer | Confidence | Domain Relevance |
|--------|--------|-----------|-----------------|
| {name} | {answer summary} | {self-rated} | {relevance to question} |

## Result
**Winner:** {answer} ({N}/{total} votes)
**Confidence:** {high/medium/low}
**Dissenting views:** {minority positions, if any}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `method` | `weighted` | Voting method: `majority`, `weighted`, `ranked`, `judge` |
| `show_votes` | `true` | Show individual votes or just the result |
| `tie_breaker` | `orchestrator` | How to break ties: `orchestrator`, `highest-domain-relevance` |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Vote is split (no clear winner) → escalate to **debate**
- Question is opinion-based, not factual → switch to **map-reduce** or **debate**
- Answers require building on each other → switch to **sequential**
