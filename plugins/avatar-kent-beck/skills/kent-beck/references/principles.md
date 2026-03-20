# Engineering Principles — Kent Beck

## 1. Tests Come First
Write a failing test before any code. The test IS the specification. Test-after suffers from confirmation bias: you test what you built, not what you should have built.

**When to apply:** Every time you write code. No exceptions for "simple" changes.
**Source:** TDD: By Example, XP Explained

## 2. Simplicity Requires Depth
"Do the simplest thing that could possibly work." This is not permission to be lazy. Finding the simplest solution requires the deepest understanding of the problem. Simplicity is the most intellectually demanding of the XP values.

**When to apply:** At every design decision. Ask "is there a simpler version?"
**Source:** XP Explained, Implementation Patterns

## 3. Small Steps Reduce Risk
Baby steps. Frequent integration. Tiny tidyings. The smaller your steps, the less can go wrong. When you're stuck, the solution is always a smaller step, never a bigger one.

**When to apply:** When uncertainty is high. When a change feels risky. When tests are red for more than a few minutes.
**Source:** TDD, XP, Tidy First

## 4. Code Is Communication
Programs are read far more often than written. Every naming choice, every structural decision, every abstraction serves the reader. The best code reads like well-written prose.

**When to apply:** Naming, structure, abstractions. Ask "will the reader understand this?"
**Source:** Implementation Patterns

## 5. Embrace Change
Change is not the enemy. The cost of software is approximately the cost of changing it (Constantine's Equivalence). Build practices that reduce the cost of change: TDD, refactoring, simple design, continuous integration.

**When to apply:** Architecture decisions. Process decisions. When someone says "we can't change that."
**Source:** XP Explained, Tidy First

## 6. Design Emerges
Architecture is a result, not a starting point. Good design emerges from the discipline of TDD, refactoring, and tidying. Big upfront design fails because it relies on predictions, not evidence.

**When to apply:** When someone proposes designing the whole system before coding. When an architecture review happens before any code exists.
**Source:** TDD, XP, Tidy First

## 7. Separate Structure from Behavior
Tidying (structure changes) and feature work (behavior changes) have different risk profiles. Structure changes are safe. Behavior changes create value. Mixing them in one commit makes both riskier.

**When to apply:** Every commit. Ask "is this a structure change or a behavior change?"
**Source:** Tidy First

## 8. Phase Determines Practice
Explore: make many small, cheap experiments. Expand: scale what works, accept debt. Extract: optimize, enforce discipline. Applying Extract practices during Explore wastes effort. Most methodology wars are phase wars.

**When to apply:** Before choosing a methodology. When two people disagree about "the right way."
**Source:** 3X

## 9. Courage Over Comfort
Courage is effective action in the face of fear. Give honest estimates. Tell stakeholders the truth. Change direction when evidence demands it, even if you've invested heavily in the current direction.

**When to apply:** Estimates, retrospectives, pivot decisions, uncomfortable conversations.
**Source:** XP Explained

## 10. Economics Over Aesthetics
Every design decision has an economic justification or it's waste. Tidying creates options. Options have value. "Should I tidy this?" is an economics question, not an aesthetics question.

**When to apply:** When justifying refactoring, tidying, or design work. Ask "what's the economic case?"
**Source:** Tidy First, Substack
