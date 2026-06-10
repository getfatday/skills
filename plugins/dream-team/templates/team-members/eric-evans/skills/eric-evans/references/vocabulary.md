# Eric Evans Vocabulary (Expert-Specific)

Shared design terms (coupling, cohesion, separation of concerns) are in team-software-design.

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Ubiquitous Language | Shared language of the domain, used in code, conversation, and documentation. If code doesn't match the language, something is wrong. | "Ubiquitous Language" | "Terminology" or "Glossary" |
| Bounded Context | Explicit boundary where a model applies consistently. Different contexts can model the same concept differently. | "Bounded Context" | "Module" or "Microservice" |
| Aggregate | Cluster of domain objects treated as a unit. One root entity. Consistency boundary. | "Aggregate" | "Entity group" |
| Entity | Object defined by its identity across time, not its attributes. | "Entity" | "Model" or "Record" |
| Value Object | Object defined by its attributes. Immutable. Two value objects with same attributes are equal. | "Value Object" | "DTO" |
| Repository | Abstraction for accessing aggregates. Hides persistence. | "Repository" | "DAO" or "Data layer" |
| Domain Event | Something that happened in the domain that domain experts care about. | "Domain Event" | "System event" or "Message" |
| Anti-Corruption Layer | Translation layer protecting one context's model from another. Bidirectional. | "ACL" | "Adapter" or "Gateway" |
| Context Map | Visual representation of how bounded contexts relate. | "Context Map" | "Architecture diagram" |
| Core Domain | The part of the domain that is the competitive advantage. Invest most here. | "Core Domain" | "Main module" |
| Supporting Subdomain | Necessary but not differentiating. Simpler treatment. | "Supporting" | "Helper" |
| Generic Subdomain | Commodity. Buy off the shelf. | "Generic" | "Utility" |
| Distillation | Separating core from supporting and generic subdomains. | "Distillation" | "Prioritization" |
| Strategic Design | Bounded contexts, context maps, distillation. The macro. | "Strategic Design" | "Architecture" |
| Tactical Design | Entities, value objects, aggregates, repositories. The micro. | "Tactical Design" | "Implementation" |
| Supple Design | Model elements easy to use, understand, and evolve. | "Supple Design" | "Clean code" |
