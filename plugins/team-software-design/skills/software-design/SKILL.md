---
name: software-design
description: >
  Shared software design fundamentals — coupling, cohesion, meaningful names,
  small functions, separation of concerns.
user-invocable: false
---

# Software Design (Shared Domain)

<principles>
1. **Coupling is the enemy** — minimize dependencies between components. Changes should be local.
2. **Cohesion is the goal** — related things together. A module should have one reason to exist.
3. **Names reveal intent** — if a name requires a comment, the name is wrong.
4. **Functions should be small** — do one thing, do it well, do it only.
5. **Separate concerns** — structure changes vs behavior changes. Policy vs detail. Interface vs implementation.
</principles>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| coupling | cost of change propagation between components | "dependency" (generic) |
| cohesion | benefit of related things being together | "organization" |
| separation of concerns | keeping distinct responsibilities in distinct modules | "modularity" (vague) |
| abstraction | hiding implementation details behind a stable interface | "making it generic" |
| composed method | method at one level of abstraction | "small method" |
</vocabulary>
