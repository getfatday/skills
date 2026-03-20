# Kent Beck Vocabulary (Expert-Specific)

Shared engineering terms (red, green, refactor, coupling, cohesion, baby steps, spike) are defined in `team-engineering/skills/engineering/references/vocabulary.md`. This file contains only Beck-specific terms.

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Tidying | A small, behavior-preserving structural improvement. Takes minutes, not hours. Always safe. Distinct from refactoring, which can be large and risky. | "I'll tidy this first" | "I'll refactor this" (if it's small) |
| Empirical design | Design decisions based on observed evidence (what actually changes together, what's actually hard to modify) rather than theoretical principles applied a priori. | "What does the evidence say?" | "What does the pattern book say?" |
| Vibe coding | AI-assisted coding where you generate more experiments and apply more careful judgment to the results. More experiments AND more care. | "Vibe coding" | "AI coding" or "copilot" |
| TCR | Test && Commit \|\| Revert. If tests pass, auto-commit. If they fail, auto-revert to last green. Forces tiny steps by making failure painful. | "Let's try TCR" | "Let's use CI" |
| Composed method | A method that operates at one level of abstraction. Either does one thing, or calls methods that each do one thing. | "This method isn't composed" | "This method is too long" |
| Guard clause | Handle edge cases at the top of a method, then handle the main case. Avoid nesting. | "Add a guard clause" | "Add an if check" |
| Symmetry | Similar things should look similar. Different things should look different. Break symmetry only when the domain demands it. | "Maintain the symmetry" | "Make it consistent" |
| Optionality | The value of being able to change cheaply in the future. Tidying creates optionality. Options have measurable economic value even if never exercised. | "This creates optionality" | "This adds flexibility" |
| Constantine's Equivalence | The cost of software is approximately equal to the cost of changing it. The economic foundation for all coupling/cohesion decisions. | "By Constantine's Equivalence..." | "Change is expensive because..." |
| 3X | Explore/Expand/Extract. Products go through three phases requiring fundamentally different strategies. | "What phase are we in?" | "What stage is the product at?" |
| Embrace change | Actively build practices that make change cheap. Change is the constant, not the exception. Active, not passive. | "Embrace change" | "Accept change" |
