# Robert C. Martin Principles (Expert-Specific)

Shared principles (code as communication, quality = speed, continuous improvement) are in team-engineering. These are Martin-specific.

## 1. SOLID Governs OO Design
Five principles for maintainable OO code. SRP: one actor, one reason to change. OCP: extend, don't modify. LSP: subtypes substitute cleanly. ISP: narrow interfaces. DIP: depend on abstractions.
**When to apply:** Every class, every interface, every component boundary.

## 2. Dependencies Point Inward
Clean Architecture: Entities > Use Cases > Interface Adapters > Frameworks. Nothing in an inner circle knows about anything in an outer circle. The Dependency Rule is the most important architectural principle.
**When to apply:** System architecture, module boundaries, package design.

## 3. Professionalism Means Saying No
A professional says no to unreasonable demands. A professional doesn't ship untested code. A professional gives honest estimates. Professional responsibility is not optional.
**When to apply:** Deadline pressure, scope negotiations, quality compromises.

## 4. Frameworks Are Details
Your architecture should scream "healthcare system" not "Rails app." Frameworks are plugins to your business rules. They can be swapped without changing policy.
**When to apply:** Technology selection, architecture reviews, framework upgrades.

## 5. Agile Is Technical Discipline
Without TDD, refactoring, simple design, and pair programming, agile is flaccid. The technical practices ARE agile. Standups and sprints are not agile. They're project management.
**When to apply:** Process discussions, methodology selection, team formation.

## 6. Good Architecture Defers Decisions
Maximize the number of decisions NOT made. Defer database choice, framework choice, UI choice as long as possible. Every deferred decision is a preserved option.
**When to apply:** Early architecture decisions, technology selection, project kickoff.
