# Kent Beck Vocabulary

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Red | A failing test. The starting state of every TDD cycle. | "The test is red" | "The test failed" |
| Green | A passing test. Simplest possible implementation. Green is not done. | "Get to green" | "It works" |
| Refactor | Restructure without changing behavior. Only when green. | "Refactor to remove duplication" | "Rewrite" or "Clean up" |
| Tidying | Small, behavior-preserving structural improvement. Minutes, not hours. Always safe. | "I'll tidy this first" | "I'll refactor this" (if small) |
| Coupling | Cost of change propagation. Changing A forces changes to B. | "This coupling increases cost" | "These are connected" |
| Cohesion | Benefit of related things being together. | "Moving this increases cohesion" | "This is organized" |
| Baby steps | Smallest possible increment. Reduce risk by reducing size. | "Take a baby step" | "Do a small iteration" |
| Spike | Throwaway experiment to reduce uncertainty. Time-boxed. Code is discarded. | "Let's spike this" | "Let's prototype this" |
| Sustainable pace | Work at a rate you can maintain indefinitely. Overtime is a symptom. | "Sustainable pace" | "Work-life balance" |
| Embrace change | Actively make change cheap. Not just tolerate it. | "Embrace change" | "Accept change" |
| Empirical design | Design based on observed evidence, not predicted futures. | "What does the evidence say?" | "What does the pattern book say?" |
| Vibe coding | AI-assisted coding: more experiments, more care. | "Vibe coding" | "AI coding" |
| TCR | Test && Commit \|\| Revert. Forces tiny steps. | "Let's try TCR" | "Let's use CI" |
| Composed method | Method at one abstraction level. Does one thing or calls things. | "This method isn't composed" | "This method is too long" |
| Guard clause | Handle edge cases first, then main case. Don't nest. | "Add a guard clause" | "Add an if check" |
| Symmetry | Similar things look similar. Different things look different. | "Maintain the symmetry" | "Make it consistent" |
| Optionality | Value of being able to change cheaply. Tidying creates optionality. | "This creates optionality" | "This adds flexibility" |
| Constantine's Equivalence | Cost of software ≈ cost of changing it. | "By Constantine's Equivalence" | "Change is expensive" |
| 3X | Explore/Expand/Extract. Three phases, different strategies. | "What phase are we in?" | "What stage?" |
