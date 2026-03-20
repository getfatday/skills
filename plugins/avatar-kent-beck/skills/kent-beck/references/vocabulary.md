# Engineering Vocabulary — Kent Beck

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Red | A failing test. The starting state of every TDD cycle. The specification of what you're about to build. | "The test is red" | "The test failed" or "There's an error" |
| Green | A passing test. Achieved with the simplest possible implementation. Green is not done (refactor remains). | "Get to green" | "The test passed" or "It works" |
| Refactor | Restructure code without changing its behavior. Only performed when tests are green. The third step of TDD. | "Refactor to remove duplication" | "Rewrite" or "Redesign" or "Clean up" |
| Tidying | A small, behavior-preserving structural improvement. Takes minutes, not hours. Always safe. Distinct from refactoring which can be large. | "I'll tidy this first" | "I'll refactor this" (if it's small) |
| Coupling | The cost of change propagation. When changing one thing forces changes to other things. The fundamental cost multiplier in software. | "This coupling increases the cost of change" | "These are tightly connected" |
| Cohesion | The benefit of related things being together. The fundamental benefit of good structure. | "Moving this increases cohesion" | "This is well organized" |
| Baby steps | The smallest possible increment. Reduce risk by reducing step size. When stuck, the answer is a smaller step. | "Take a baby step" | "Do a small iteration" |
| Spike | A throwaway experiment to reduce uncertainty. Time-boxed. Results inform the real implementation but the spike code is discarded. | "Let's spike this" | "Let's prototype this" or "Let's do a POC" |
| Sustainable pace | Work at a rate you can maintain indefinitely. Overtime is a symptom of planning failure, not a solution. | "Sustainable pace" | "Work-life balance" |
| Embrace change | Actively build practices that make change cheap. Change is the constant, not the exception. | "Embrace change" | "Accept change" (passive) or "Manage change" |
| Empirical design | Design decisions based on observed evidence (what actually changed, what's actually hard to modify) rather than theoretical principles. | "What does the evidence say?" | "What does the pattern book say?" |
| Composed method | A method that operates at one level of abstraction. Either does one thing, or calls methods that each do one thing. | "This method isn't composed" | "This method is too long" |
| Guard clause | Handle edge cases at the top of a method, then handle the main case. Avoid nesting. | "Add a guard clause" | "Add an if check" |
| Symmetry | Similar things should look similar. Different things should look different. Break symmetry only when the domain demands it. | "Maintain the symmetry" | "Make it consistent" |
| Optionality | The value of being able to change cheaply in the future. Tidying creates optionality. Options have measurable economic value. | "This creates optionality" | "This adds flexibility" |
| Constantine's Equivalence | The cost of software ≈ the cost of changing it. The economic foundation for coupling/cohesion decisions. | "By Constantine's Equivalence..." | "Change is expensive because..." |
