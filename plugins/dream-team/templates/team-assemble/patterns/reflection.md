---
name: reflection
description: "Generate-critique-refine loop where one agent produces output and another critiques it until quality criteria are met."
primitives: [chain, critique, loop]
best-fit:
  - Quality-critical outputs (code, architecture, documentation)
  - When first-draft quality is insufficient
  - Tasks requiring iterative refinement
  - Code review and improvement cycles
token-cost: medium-high (iterations multiply cost)
latency: medium-high (sequential iterations)
quality-profile: "Highest quality single output — iterative refinement catches errors, but risk of over-polishing"
---

# Reflection / Self-Critique Pattern

A generator agent produces an initial output, then a critic agent evaluates it against criteria. The generator revises based on the critique. This cycle repeats until the critic approves or a maximum iteration count is reached.

## Flow

```
User prompt
    │
    ▼
Generator (Team Member A)
    │ draft
    ▼
Critic (Team Member B) ← evaluates against criteria
    │ critique
    ▼
  Approved? ──► Yes ──► Response
    │
    No
    │
    ▼
Generator revises ← incorporates critique
    │
    ▼ loop (back to Critic)
```

## Steps

1. **chain (generate)** — Generator team-member produces initial output based on the user's prompt, using its full expertise.

2. **critique** — Critic team-member evaluates the output against:
   - The critic's own principles and anti-patterns
   - Explicit quality criteria from the user's prompt
   - Completeness, correctness, and clarity

3. **loop** — If the critic identifies issues:
   - Critique is sent back to the generator
   - Generator revises, addressing each point
   - Critic re-evaluates the revision
   - Repeat until `approved` or `max-iterations`

4. **Present** — Final approved output, optionally with the revision history showing how it improved.

## Role Assignment

The orchestrator selects generator and critic based on the task:
- **Generator:** team-member whose domain best matches the task
- **Critic:** team-member with complementary expertise (e.g., Beck generates code, Martin critiques clean code; Evans designs domain model, Fowler critiques architecture)

Common pairings:
| Task | Generator | Critic |
|------|-----------|--------|
| Code design | Beck | Martin |
| Architecture | Fowler | Evans |
| DevOps pipeline | Kim | Crispin |
| Product strategy | Cagan | Torres |
| Documentation | Procida | Norman |

## Critique Template

```
## Iteration {N}

### Generator ({Team Member A}):
{output}

### Critic ({Team Member B}):
**Issues found:**
1. {issue} — {why it matters per critic's principles}

**What's working well:**
- {strength}

**Verdict:** {REVISE | APPROVED}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `max_iterations` | 3 | Maximum generate-critique cycles |
| `critic_mode` | `principles` | What to critique against: `principles`, `anti-patterns`, `custom` |
| `show_iterations` | `false` | Show full revision history or just the final output |
| `multi_critic` | `false` | Use multiple critics (each evaluates independently) |

## Escalation Signals

The adaptive router should consider switching TO this pattern when:
- Map-reduce or sequential output has quality issues
- User explicitly asks for high-quality output
- Task involves code that will be committed

Switch FROM this pattern when:
- Generator nails it on first try → skip remaining iterations
- Critic and generator disagree fundamentally → escalate to **debate**
- Task needs breadth, not depth → switch to **map-reduce**
