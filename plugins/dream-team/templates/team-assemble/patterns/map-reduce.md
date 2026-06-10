---
name: map-reduce
description: "Fan out a prompt to all selected agents in parallel, then synthesize their responses into a unified answer."
primitives: [fan-out, fan-in]
best-fit:
  - Broad perspective gathering
  - Questions spanning multiple domains
  - When all agents' views are equally valuable
  - Low urgency, high thoroughness
token-cost: high (N parallel calls + synthesis)
latency: low (parallel execution)
quality-profile: "Comprehensive but can be shallow — each agent only gets one shot"
---

# Map-Reduce Pattern

The current default pattern. Broadcasts the user's prompt to all selected team-members in parallel, collects their independent responses, and synthesizes them into a unified answer.

## Flow

```
User prompt
    │
    ├──► Team Member A ──┐
    ├──► Team Member B ──┤
    ├──► Team Member C ──┤  fan-out (parallel)
    └──► Team Member D ──┘
                    │
              fan-in (synthesize)
                    │
                Response
```

## Steps

1. **fan-out** — Send the user's prompt to all selected team-members simultaneously via parallel `SendMessage`. Each team-member responds independently using its persona, principles, and vocabulary.

2. **fan-in** — Orchestrator synthesizes all responses:
   - Identify areas of **agreement** across team-members
   - Identify areas of **disagreement** with reasoning from each side
   - Produce **actionable recommendations** that integrate the team's expertise

3. **Checkpoint** — Use AskUserQuestion after the synthesis:
   - "Dig deeper with {team-member name}" — switch to moe-routing for 1:1 with that expert
   - "Debate {specific point}" — switch to debate pattern on an area of disagreement
   - "Get a different team's take" — re-run with different team-members
   - "Apply the recommendations" — begin implementation
   - "I'm good" — end

## Synthesis Template

```
## {Team Member Name}
{Team Member's response in their voice}

---
[repeat for each team-member]

## Synthesis
**Consensus:** {where team-members agree}
**Divergence:** {where they disagree, with reasoning}
**Recommendation:** {integrated action items}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `synthesis_mode` | `merge` | How to combine: `merge`, `rank`, or `diff` |
| `include_individual` | `true` | Show each team-member's individual response before synthesis |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Strong disagreement detected → escalate to **debate**
- One team-member clearly dominates relevance → narrow to **moe-routing**
- Output quality concerns → inject **reflection** loop
