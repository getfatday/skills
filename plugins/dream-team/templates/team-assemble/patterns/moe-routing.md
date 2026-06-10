---
name: moe-routing
description: "Lightweight router dispatches the task to the single best specialist agent. Fast and token-efficient."
primitives: [route]
best-fit:
  - Clear single-domain questions
  - When speed matters most
  - Simple queries that don't need multiple perspectives
  - Follow-up questions directed at a specific expertise
token-cost: lowest (single agent)
latency: lowest (single inference)
quality-profile: "Fast and focused — deep expertise from one specialist, but no cross-pollination or error checking"
---

# Mixture-of-Experts Routing Pattern

A lightweight router classifies the task and dispatches it to the single most relevant specialist. No multi-agent coordination — just fast, targeted expertise. This is the "MoE at macro level" equivalent.

## Flow

```
User prompt
    │
    ▼
Router (classify + select)
    │
    ▼
Best-fit Team Member
    │
    ▼
Response
```

## Steps

1. **route** — Orchestrator analyzes the prompt and matches it against each available team-member's `domains[]`:
   - Extract key topics, intent, and domain signals from the prompt
   - Score each team-member by domain overlap
   - Select the highest-scoring team-member
   - If confidence is below threshold, fall back to **map-reduce**

2. **Dispatch** — Send the full prompt to the selected team-member. The team-member responds using its complete persona (principles, voice, vocabulary).

3. **Present** — Return the specialist's response directly. Note which specialist was selected and why.

4. **Checkpoint** — Use AskUserQuestion after the response:
   - "Dig deeper on this topic" — continue the 1:1 with the same team-member
   - "Get other perspectives" — switch to map-reduce with additional team-members
   - "Challenge this view" — switch to reflection (add a critic team-member)
   - "I'm good" — end

   The team-member stays in character for follow-ups. Each follow-up response should end with another AskUserQuestion to keep the consultation flowing.

## Routing Template

```
**Routed to:** {Team Member Name} (domains: {relevant domains})
**Confidence:** {high/medium}
**Rationale:** {why this team-member is the best fit}

---

{Team Member's response in character}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `fallback_threshold` | 0.6 | Confidence below this triggers fallback to map-reduce |
| `show_routing` | `true` | Show which team-member was selected and why |
| `fallback_pattern` | `map-reduce` | Pattern to use when routing confidence is low |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Routing confidence is low (ambiguous domain) → fall back to **map-reduce**
- User asks for "other perspectives" → switch to **map-reduce** or **round-robin**
- Response quality is uncertain → inject **reflection** with a second team-member as critic
