# Software Design Vocabulary (Shared)

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Coupling | Cost of change propagation. When changing A forces changes to B. The fundamental cost multiplier. | "This coupling increases cost" | "These are connected" |
| Cohesion | Benefit of related things being together. The fundamental benefit of good structure. | "Moving this increases cohesion" | "This is organized" |
| Separation of concerns | Keeping distinct responsibilities in distinct modules. Structure vs behavior. Policy vs detail. | "Separate the concerns" | "Make it modular" |
| Abstraction | Hiding implementation details behind a stable interface. Not "making it generic." | "Abstract behind an interface" | "Make it flexible" |
| Composed method | Method operating at one level of abstraction. Does one thing or calls things. | "This isn't composed" | "This is too long" |
| Guard clause | Handle edge cases first, then main case. Don't nest. | "Add a guard clause" | "Add an if check" |
| Symmetry | Similar things look similar. Different things look different. | "Maintain symmetry" | "Make it consistent" |
