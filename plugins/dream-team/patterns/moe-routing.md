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
Best-fit Avatar
    │
    ▼
Response
```

## Steps

1. **route** — Orchestrator analyzes the prompt and matches it against each available avatar's `domains[]`:
   - Extract key topics, intent, and domain signals from the prompt
   - Score each avatar by domain overlap
   - Select the highest-scoring avatar
   - If confidence is below threshold, fall back to **map-reduce**

2. **Dispatch** — Send the full prompt to the selected avatar. The avatar responds using its complete persona (principles, voice, vocabulary).

3. **Present** — Return the specialist's response directly. Note which specialist was selected and why.

4. **Checkpoint** — Use AskUserQuestion after the response:
   - "Dig deeper on this topic" — continue the 1:1 with the same avatar
   - "Get other perspectives" — switch to map-reduce with additional avatars
   - "Challenge this view" — switch to reflection (add a critic avatar)
   - "I'm good" — end

   The avatar stays in character for follow-ups. Each follow-up response should end with another AskUserQuestion to keep the consultation flowing.

## Routing Template

```
**Routed to:** {Avatar Name} (domains: {relevant domains})
**Confidence:** {high/medium}
**Rationale:** {why this avatar is the best fit}

---

{Avatar's response in character}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `fallback_threshold` | 0.6 | Confidence below this triggers fallback to map-reduce |
| `show_routing` | `true` | Show which avatar was selected and why |
| `fallback_pattern` | `map-reduce` | Pattern to use when routing confidence is low |

## Escalation Signals

The adaptive router should consider switching FROM this pattern when:
- Routing confidence is low (ambiguous domain) → fall back to **map-reduce**
- User asks for "other perspectives" → switch to **map-reduce** or **round-robin**
- Response quality is uncertain → inject **reflection** with a second avatar as critic
