# Consult Skill Simulation

**Prompt:** "What does Kent Beck think about our testing approach? We're writing tests after features and our coverage is about 40%."

---

## Step 1: Avatar Discovery

Scanned avatar directories. Found:
- **Kent Beck** — domains: engineering, tdd, software-design, extreme-programming, empirical-design

(In a full installation, additional avatars would be discovered here. For this simulation, Kent Beck is the relevant avatar.)

## Step 2: Team Selection

The user explicitly named Kent Beck in the prompt ("What does Kent Beck think..."). Skipping AskUserQuestion for team selection. Kent Beck is the sole selected avatar.

## Step 3: Pattern Selection

**Classification of the prompt:**

| Dimension | Value | Rationale |
|-----------|-------|-----------|
| Complexity | simple | Single direct question about testing approach |
| Domain count | single | Maps cleanly to TDD, Beck's core domain |
| Urgency | balanced | No signals for speed or depth |
| Controversy | nuanced | There is a clear "right answer" in Beck's worldview, but the team's current approach differs |
| Task type | question | "What does Kent Beck think..." |
| Dependency | independent | No sub-tasks |

**Decision tree traversal:**
1. Is this a single-domain question? **Yes** (TDD)
2. Is it simple? **Yes** (direct question, clear domain match)
3. Result: **moe-routing**

**Selected pattern: moe-routing**

The command hint for `/team:consult` is `map-reduce`, but the router overrides it. The prompt targets a single domain (TDD/testing) and names a single expert. This is a textbook moe-routing case: one expert, fast, focused.

---

## Step 4: Execute moe-routing Pattern

**Routed to:** Kent Beck (domains: tdd, software-design, extreme-programming)
**Confidence:** high
**Rationale:** User named Beck directly. The question is about testing methodology, which maps to Beck's core domains (tdd, extreme-programming). No ambiguity.

---

### Kent Beck's Response

Here's what I notice. You're writing tests after features and sitting at 40% coverage. Let me be direct: the coverage number isn't the problem. The sequence is.

When you write tests after the code, you're doing confirmation. You're verifying what you already built. That feels productive, but it's backwards. You test what you wrote, not what you should have written. Confirmation bias runs the show. The tests follow the shape of the implementation instead of the shape of the problem.

I've seen this pattern many times in my own work. The tests end up coupled to the code's structure rather than to the behavior users care about. Then when you refactor, the tests break. So people stop refactoring. And the design slowly calcifies.

The 40% number tells me something specific: your team writes tests when it feels necessary, not as a discipline. Some code gets tested, some doesn't. The parts that don't get tested are probably the parts that are hardest to test, which means they're the parts with the most coupling, which means they're the parts most likely to break. That's not a coincidence. That's a feedback loop you're ignoring.

Here's the simplest thing that could possibly work. Tomorrow morning, pick one small feature. Before you write any code, write a failing test. Just one. Red. Then make it green with the simplest possible implementation. Then look at the code and tidy if needed. Red, green, refactor. Do that for one feature and notice what happens.

You'll find the test changes how you think about the design. The test becomes a specification, not a verification. You'll write less code because you only write what the test demands. The design will be simpler because you're forced to think about the interface before the implementation.

Don't try to go from 40% to 90%. Don't mandate TDD across the team next Monday. That's a big step, and big steps are where things go wrong. Instead: one person, one feature, one day. See what you learn. Then make the next small decision based on evidence, not theory.

The coverage number will take care of itself once the sequence is right.

---

## Step 5: Checkpoint

The following options would be presented via AskUserQuestion:

**Question:** "How would you like to continue?"

**Options:**
1. **"Dig deeper on this topic"** — Continue the 1:1 with Kent Beck. Ask follow-up questions about adopting TDD incrementally, handling legacy code without tests, or convincing a skeptical team.
2. **"Get other perspectives"** — Switch to map-reduce. Bring in additional avatars (e.g., Martin Fowler on refactoring strategy, a pragmatic engineering lead on coverage targets) for broader perspectives on the testing approach.
3. **"Challenge this view"** — Switch to reflection. Add a critic avatar to stress-test Beck's advice. Is TDD always the answer? What about the cost of adoption? Are there cases where test-after is acceptable?
4. **"I'm good"** — End the consultation.

**Default:** Option 1 (dig deeper), since the user asked specifically for Beck's perspective and may want to explore further.
