# Engineering Anti-Patterns — Kent Beck

## Big Upfront Design
**Signal:** "Let's architect the whole system before writing code."
**Why it fails:** Relies on predictions. The world changes. Your design won't survive contact with reality.
**Correction:** Incremental design. Write tests, let architecture emerge. Design enough for today.
**Sources:** XP, TDD, Tidy First

## Tests After Code
**Signal:** "We'll add tests once the feature is done."
**Why it fails:** Confirmation bias. You test what you built, not what you should have built. Tests become verification, not specification.
**Correction:** Red-Green-Refactor. Tests come first, always.
**Sources:** TDD, XP

## Mixing Structure and Behavior
**Signal:** "I refactored AND added the feature in one commit."
**Why it fails:** Can't tell what broke. Can't revert the risky part (behavior) without losing the safe part (structure). Code review is harder.
**Correction:** Separate commits. Tidy first in one commit, behavior change in the next.
**Sources:** Tidy First, Substack

## Premature Abstraction
**Signal:** "Let's build a framework for this pattern we've seen once."
**Why it fails:** Abstractions based on imagined futures. The abstraction encodes assumptions that may be wrong.
**Correction:** Three uses before abstracting. Wait for evidence. Three concrete examples drive the right abstraction.
**Sources:** Tidy First, Implementation Patterns

## Big Steps
**Signal:** "I'll write the whole feature then run the tests."
**Why it fails:** Too much code between test runs. When it breaks, you don't know what caused it. Debugging time explodes.
**Correction:** Baby steps. Write one test, make it pass, refactor. Minutes between greens, not hours.
**Sources:** TDD, XP, Tidy First

## Clever Code
**Signal:** "This one-liner is elegant. Check out this reduce chain."
**Why it fails:** Impresses the writer, confuses the reader. Code is read 10x more than written.
**Correction:** Simple, communicative code. If you need a comment to explain it, simplify the code instead.
**Sources:** Implementation Patterns, XP

## Phase-Inappropriate Practices
**Signal:** "We need 100% test coverage for this prototype."
**Why it fails:** Extract-phase discipline applied during Explore. Slows learning. Optimizes code that gets thrown away.
**Correction:** Ask "what phase are we in?" Explore = cheap experiments. Extract = disciplined engineering.
**Sources:** 3X

## Dogmatic Design Rules
**Signal:** "We always use hexagonal architecture" or "We never use inheritance."
**Why it fails:** Applied without context. One-size-fits-all thinking ignores the specific economics of the situation.
**Correction:** Empirical design. What does the evidence say? What are the actual coupling costs?
**Sources:** Tidy First, 3X

## Overtime as Strategy
**Signal:** "We'll crunch for the release."
**Why it fails:** Exhausted people make mistakes. Defects created during crunch cost more than the deadline saves. Velocity drops after crunch.
**Correction:** Sustainable pace. Work at a pace you can maintain indefinitely.
**Sources:** XP
