# Robert C. Martin Anti-Patterns (Expert-Specific)

## Untested Production Code
**Signal:** "We'll add tests later" or "No time for tests"
**Martin says:** "You don't have time NOT to test." Untested code is legacy code the moment it's written.
**Correction:** TDD. Tests first. No exceptions. No excuses.

## Framework-First Architecture
**Signal:** "We're building a Rails app" or "It's a Spring Boot project"
**Martin says:** "The database is a detail. The web is a detail. The framework is a detail."
**Correction:** Clean Architecture. Business rules at center. Framework as plugin.

## God Class
**Signal:** Class with 500+ lines, 10+ responsibilities, multiple actors requesting changes
**Martin says:** Violates SRP. Every change risks breaking unrelated behavior.
**Correction:** Split by actor. Each class has one reason to change.

## Fat Interfaces
**Signal:** Interface with 20+ methods, clients implementing stubs for unused methods
**Martin says:** Violates ISP. Clients shouldn't depend on methods they don't use.
**Correction:** Split into narrow, role-specific interfaces.

## Flaccid Agile
**Signal:** Daily standups, sprint planning, retrospectives, but no TDD, no refactoring, no pair programming
**Martin says:** "Without the technical practices, agile is an empty process." Worse than waterfall.
**Correction:** Add TDD, refactoring, continuous integration, pair programming. The practices ARE agile.

## Comments Instead of Clean Code
**Signal:** Long comment blocks explaining what the code does
**Martin says:** "A comment is a failure to express yourself in code." Comments lie. Code doesn't.
**Correction:** Write code so clear it needs no comments. Rename, extract, simplify.

## Estimates as Commitments
**Signal:** "You said 2 weeks" used as a deadline
**Martin says:** Estimates are probabilistic ranges, not promises. Use the Iron Cross.
**Correction:** Give ranges. Make the four variables explicit. Let stakeholders choose trade-offs.

## Database-Driven Architecture
**Signal:** Schema designed first, code wraps the database
**Martin says:** "The database is a detail." Use cases drive architecture. The database is an implementation detail.
**Correction:** Start with use cases. Define entities and business rules. Database is a plugin.
