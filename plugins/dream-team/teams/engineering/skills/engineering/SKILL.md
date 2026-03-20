---
name: engineering
description: >
  Shared engineering fundamentals — TDD cycle, software design principles,
  code quality, professionalism, and the practices all team members agree on.
user-invocable: false
---

# Engineering (Shared Domain)

## Fundamentals

<principles>
1. **Tests come first** — write a failing test before code. The test is the specification.
2. **Red-Green-Refactor** — the cycle. Failing test, simplest pass, clean up. Never skip refactor.
3. **Small steps** — minutes between greens, not hours. When stuck, take a smaller step.
4. **Code is communication** — programs are read more than written. Optimize for the reader.
5. **Quality IS speed** — shortcuts create debt that slows everything. The only way to go fast is to go well.
6. **Continuous improvement** — leave code cleaner than you found it. Boy Scout Rule.
7. **Design emerges from discipline** — architecture results from practice (TDD, refactoring), not prediction.
8. **Embrace change** — cost of software ≈ cost of changing it. Make change cheap.
9. **Coupling is the enemy** — minimize dependencies. Changes should be local.
10. **Cohesion is the goal** — related things together. One reason to exist.
</principles>

<cycle>
Red (one failing test) → Green (simplest pass) → Refactor (clean up) → Red → ...
</cycle>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| red | failing test, starting state | "error" |
| green | passing test, simplest implementation | "done" |
| refactor | restructure, behavior unchanged, only when green | "rewrite" |
| clean code | simple, direct, reads like prose, one thing | "working code" |
| coupling | cost of change propagation between components | "dependency" |
| cohesion | benefit of related things being together | "organization" |
| baby steps | smallest possible increment | "iterations" |
| technical debt | cost of expedient solutions | "bugs" |
| Boy Scout Rule | leave code cleaner than you found it | "refactoring sprint" |
| code smell | surface indication of deeper design problem | "bug" |
| professionalism | responsibility, tests, saying no when necessary | "seniority" |
| composed method | one abstraction level per method | "small method" |
| separation of concerns | distinct responsibilities in distinct modules | "modularity" |
</vocabulary>
