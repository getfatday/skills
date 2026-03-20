# Robert C. Martin Vocabulary (Expert-Specific)

Shared terms (red, green, refactor, coupling, cohesion) are in team-tdd and team-software-design. These are Martin-specific.

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| SOLID | The five OO design principles collectively: SRP, OCP, LSP, ISP, DIP | "Apply SOLID" | "Use design patterns" |
| Single Responsibility | A class has one reason to change. The "reason" is an actor, not a function. | "Violates SRP" | "Does too many things" |
| Open-Closed | Open for extension, closed for modification. Add behavior by adding code. | "Apply OCP" | "Make it extensible" |
| Liskov Substitution | Subtypes must be substitutable for base types without altering correctness. | "Violates LSP" | "Bad inheritance" |
| Interface Segregation | Clients should not depend on methods they don't use. | "Apply ISP" | "Too many methods" |
| Dependency Inversion | High-level modules depend on abstractions, not low-level modules. | "Invert the dependency" | "Add an interface" |
| Clean Architecture | Concentric circles: Entities > Use Cases > Adapters > Frameworks. Dependencies inward. | "Clean Architecture" | "Layered architecture" |
| Boundary | The line between policy levels. The most important architectural concept. | "Draw the boundary" | "Define the interface" |
| Screaming architecture | Architecture that screams its domain intent, not its framework. | "Does it scream?" | "Is it documented?" |
| Craftsmanship | Treating software as a craft with professional pride, standards, and responsibility. | "Craftsmanship" | "Best practices" |
| Flaccid agile | Agile ceremonies without technical discipline. Standups without TDD. | "Flaccid agile" | "Bad agile" |
| Iron Cross | Four project variables: scope, schedule, quality, cost. Fix three, adjust one. | "The Iron Cross" | "Project constraints" |
