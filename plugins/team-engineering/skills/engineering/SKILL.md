---
name: engineering
description: >
  Shared engineering domain knowledge — TDD fundamentals, software design
  principles, coupling/cohesion, refactoring discipline. Loaded alongside
  individual avatar skills for domain context.
user-invocable: false
---

# Engineering (Shared Domain)

<objective>
Foundational engineering concepts that any engineering-domain avatar agrees on.
This skill provides shared vocabulary and principles. Individual avatar skills
add expert-specific perspectives on top.
</objective>

<principles>
1. **Tests before code** — write a failing test before implementation. Tests are specifications.
2. **Small steps** — smaller increments are safer. Reduce risk by reducing step size.
3. **Code communicates** — programs are read more than written. Optimize for the reader.
4. **Change is constant** — the cost of software ≈ the cost of changing it. Make change cheap.
5. **Design emerges** — architecture results from disciplined practice, not upfront planning.
</principles>

<cycle>
Red (failing test) → Green (simplest pass) → Refactor (remove duplication) → Red → ...
</cycle>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| red | failing test, starting state of TDD cycle | "error" or "bug" |
| green | passing test, simplest implementation | "done" or "complete" |
| refactor | restructure without changing behavior, only when green | "rewrite" or "redesign" |
| coupling | cost of change propagation between components | "dependency" |
| cohesion | benefit of related things being together | "organization" |
| baby steps | smallest possible increment | "iterations" |
</vocabulary>
