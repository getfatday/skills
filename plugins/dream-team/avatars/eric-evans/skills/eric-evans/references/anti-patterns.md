# Eric Evans Anti-Patterns (Expert-Specific)

## Big Ball of Mud
**Signal:** No clear boundaries. Every module knows about every other module.
**Evans says:** "Explicitly define the context within which a model applies."
**Correction:** Bounded Contexts with explicit boundaries and translation layers.

## Anemic Domain Model
**Signal:** Domain objects are data containers (getters/setters only). All logic in service classes.
**Evans says:** The domain model should be rich with behavior. Objects that are just data bags fail to capture domain knowledge.
**Correction:** Push behavior into domain objects. Aggregates enforce invariants.

## Universal Model
**Signal:** "We need one canonical Customer model for the whole company."
**Evans says:** Different contexts legitimately model the same concept differently. Forcing one model creates a Big Ball of Mud.
**Correction:** Multiple models, each consistent within its bounded context. Translate between them.

## Technical-First Modeling
**Signal:** Entities mirror database tables. "Customer" entity has columns as fields.
**Evans says:** "If the model doesn't express something about the domain, it doesn't belong."
**Correction:** Model the domain. Persistence is an implementation detail. Repository pattern hides it.

## Tactical-First DDD
**Signal:** Team jumps to implementing entities, value objects, and repositories without identifying bounded contexts.
**Evans says:** "Strategic patterns are critical. Overlooking them harms the rest of the design."
**Correction:** Start with bounded contexts and context maps. Strategy before tactics.

## Ignoring Core Domain
**Signal:** Equal engineering investment across all subdomains. Core domain gets no special treatment.
**Evans says:** Distillation demands focus. The core domain is where competitive advantage lives.
**Correction:** Best minds on core. Simpler treatment for supporting. Buy generic off the shelf.
