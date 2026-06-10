# Conversation Primitives

Atomic operations that compose into conversation patterns. The orchestrator reads this file to understand what building blocks are available.

## Primitives

### fan-out

Send the same prompt to N agents in parallel. Each agent processes independently.

- **Input:** prompt, list of agent IDs
- **Output:** list of responses (one per agent)
- **Implementation:** parallel `SendMessage` to each teammate
- **Token cost:** N × prompt_tokens
- **Latency:** max(agent_response_times) — parallel, so wall-clock = slowest agent

### fan-in

Synthesize N agent responses into a single consolidated output. The orchestrator merges, reconciles, and produces a unified answer.

- **Input:** list of responses, synthesis instructions
- **Output:** single synthesized response
- **Implementation:** orchestrator reads all responses, applies synthesis template
- **Variants:**
  - `merge` — combine all perspectives into one narrative
  - `rank` — order responses by relevance/quality
  - `diff` — highlight agreements and disagreements

### chain

Pass output from agent A as input to agent B. Sequential handoff.

- **Input:** prompt, ordered list of agent IDs
- **Output:** final agent's response (with accumulated context)
- **Implementation:** sequential `SendMessage`, each receiving prior agent's output
- **Token cost:** sum of all stages (context grows at each step)
- **Latency:** sum(agent_response_times) — fully sequential

### critique

One agent evaluates another agent's output against specified criteria.

- **Input:** output to critique, criteria, critic agent ID
- **Output:** critique (issues found, scores, suggestions)
- **Implementation:** `SendMessage` to critic with output + criteria
- **Criteria types:**
  - `principles` — does it align with the critic's principles?
  - `anti-patterns` — does it violate known anti-patterns?
  - `correctness` — is the content factually/logically sound?
  - `completeness` — are there gaps or missing perspectives?

### route

Classify a task and select the best agent(s) to handle it. Lightweight dispatch.

- **Input:** task description, list of available agents with their domains
- **Output:** selected agent ID(s), confidence score, routing rationale
- **Implementation:** orchestrator matches task keywords/intent against agent `domains[]`
- **Routing strategies:**
  - `best-match` — single agent with highest domain overlap
  - `top-k` — top K agents by relevance
  - `threshold` — all agents above a confidence threshold

### vote

Collect independent judgments from N agents and determine consensus.

- **Input:** question, list of agent IDs, voting method
- **Output:** tally, winner, confidence
- **Implementation:** `fan-out` the question, then count/compare responses
- **Voting methods:**
  - `majority` — most common answer wins
  - `weighted` — agents weighted by domain relevance
  - `ranked` — agents rank options, Borda count

### share

Write information to a shared workspace visible to all agents.

- **Input:** key, value, author agent ID
- **Output:** updated workspace state
- **Implementation:** orchestrator maintains a workspace object, agents write via `SendMessage`
- **Workspace is:** a structured key-value store the orchestrator manages in its context

### monitor

Check shared workspace state and determine if an agent should activate.

- **Input:** workspace state, agent's activation criteria
- **Output:** boolean (activate or not), relevant workspace entries
- **Implementation:** orchestrator evaluates each agent's activation rules against current workspace

### recurse

An agent decomposes a task and spawns sub-agents to handle sub-tasks.

- **Input:** task, decomposition strategy, max depth
- **Output:** aggregated results from sub-agent tree
- **Implementation:** agent uses `Agent` tool to spawn sub-agents, which may recurse further
- **Safety:** max depth limit (default: 3), total agent limit (default: 10)

### loop

Repeat a step or sequence until a condition is met.

- **Input:** step(s) to repeat, exit condition, max iterations
- **Output:** final result when condition met
- **Implementation:** orchestrator re-executes step(s), checks condition after each iteration
- **Exit conditions:**
  - `approved` — critic gives passing score
  - `converged` — output stops changing significantly
  - `max-iterations` — hard limit reached (default: 3)
