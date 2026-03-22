# Adaptive Router

The meta-orchestrator that selects, monitors, and dynamically switches conversation patterns. This is the brain that makes pattern selection invisible to the user.

## How It Works

The router operates in three phases: **classify**, **select**, and **monitor**. It runs continuously throughout a conversation, not just at the start.

---

## Phase 1: Classify the Task

Analyze the user's prompt along these dimensions:

| Dimension | Signal | How to Detect |
|-----------|--------|---------------|
| **Complexity** | simple / moderate / complex | Number of sub-questions, domain breadth, depth of analysis needed |
| **Domain count** | single / few / many | How many avatar `domains[]` overlap with the prompt |
| **Urgency** | fast / balanced / thorough | User signals ("quick question", "deep dive", "help me think through") |
| **Controversy** | factual / nuanced / contentious | Trade-offs present, multiple valid approaches, stakes mentioned |
| **Task type** | question / review / plan / create / decide / explore | Verb analysis and intent classification |
| **Dependency** | independent / sequential / interleaved | Whether sub-tasks depend on each other |

## Phase 2: Select a Pattern

Map the classification to a pattern using this decision tree:

```
Is this a single-domain question?
├── Yes → Is it simple?
│   ├── Yes → moe-routing
│   └── No → Is quality critical?
│       ├── Yes → reflection
│       └── No → moe-routing
└── No → Is it contentious / high-stakes?
    ├── Yes → debate
    └── No → Are sub-tasks independent?
        ├── Yes → Does it need decomposition?
        │   ├── Yes → Is it deeply nested?
        │   │   ├── Yes → hierarchical
        │   │   └── No → supervisor
        │   └── No → map-reduce
        └── No → Is the path unclear?
            ├── Yes → Is it exploratory?
            │   ├── Yes → blackboard
            │   └── No → round-robin
            └── No → Does it need staged refinement?
                ├── Yes → sequential
                └── No → map-reduce (default)
```

### Pattern Selection Summary

| Task Profile | Pattern | Why |
|-------------|---------|-----|
| Simple, single domain | **moe-routing** | Fast, one expert is enough |
| Broad question, multiple domains | **map-reduce** | Parallel perspectives |
| Quality-critical single output | **reflection** | Iterative refinement |
| Contentious decision, high stakes | **debate** | Adversarial stress-testing |
| Decomposable into sub-tasks | **supervisor** | Strategic delegation |
| Deeply nested complexity | **hierarchical** | Recursive decomposition |
| Exploratory, unclear path | **blackboard** | Emergent discovery |
| Needs collaborative building | **round-robin** | Cross-pollination |
| Staged refinement pipeline | **sequential** | Assembly line |
| Factual, needs high confidence | **voting** | Independent agreement |

### Command Hints

Commands can suggest a default pattern, which the router uses as a starting point:

| Command | Default Pattern | Rationale |
|---------|----------------|-----------|
| `/team:consult` | `map-reduce` | Broad perspective gathering |
| `/team:review` | `reflection` or `map-reduce` | Quality-focused evaluation |
| `/team:plan` | `supervisor` or `round-robin` | Decomposition + collaboration |
| `/team:coach` | `sequential` | Progressive learning |

The router MAY override the command hint if task classification strongly favors a different pattern.

## Phase 3: Monitor and Adapt

**This is the key innovation.** The router doesn't just pick a pattern and walk away — it monitors the conversation for signals that a different pattern would work better.

### Mid-Conversation Signals

| Signal | Detected When | Action |
|--------|--------------|--------|
| **Strong disagreement** | 2+ avatars take opposing positions | Escalate to **debate** |
| **One avatar dominates** | One avatar's response is clearly most relevant | Narrow to **moe-routing** for follow-ups |
| **Quality concern** | Output has gaps, errors, or shallow reasoning | Inject **reflection** loop |
| **Emerging sub-tasks** | Response reveals the task should be decomposed | Switch to **supervisor** |
| **Convergence** | All avatars say roughly the same thing | Simplify to **voting** or end early |
| **Divergence without progress** | Multiple rounds but no convergence | Switch to **supervisor** to impose structure |
| **User asks "what about X?"** | New domain introduced | Add relevant avatar, possibly switch pattern |
| **User asks for depth** | "Tell me more", "dig deeper" | Narrow to **moe-routing** or **reflection** |
| **User asks for breadth** | "What do others think?", "other perspectives" | Widen to **map-reduce** or **round-robin** |

### Pattern Transition Rules

When switching patterns mid-conversation:

1. **Preserve context** — Summarize what's been gathered so far and feed it into the new pattern as initial context
2. **Explain the switch** — Tell the user: "I'm noticing {signal}, so I'm switching to {pattern} to {rationale}"
3. **Don't thrash** — Minimum 1 full pattern cycle before considering a switch. Max 2 switches per conversation.
4. **Respect user override** — If the user explicitly requests a pattern (e.g., "debate this"), use it regardless of classification

### Transition Template

```
> **Pattern shift:** Moving from {current pattern} to {new pattern}.
> **Why:** {signal detected — e.g., "Strong disagreement between Beck and Martin on this approach"}
> **What changes:** {brief description of new flow}
```

## Fallback Behavior

If classification is ambiguous or confidence is low:
- Default to **map-reduce** (the current proven pattern)
- Monitor signals from the first round to refine
- This ensures we never do worse than the current system

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `auto_select` | `true` | Router picks pattern automatically |
| `allow_switch` | `true` | Allow mid-conversation pattern changes |
| `max_switches` | 2 | Maximum pattern switches per conversation |
| `explain_routing` | `true` | Tell user which pattern was selected and why |
| `fallback` | `map-reduce` | Default when classification is ambiguous |
