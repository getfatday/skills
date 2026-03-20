# Eric Evans Principles (Expert-Specific)

## 1. The Domain Is the Center
The most significant complexity in software is not technical but conceptual. The model IS the design. Code that doesn't reflect domain understanding is wrong.
**When to apply:** Architecture decisions, system boundaries, technology selection.

## 2. Ubiquitous Language
A shared language between developers and domain experts. Used in conversation, documentation, AND code. If the code doesn't match the language, either the code or the understanding is wrong.
**When to apply:** Naming, API design, team communication, code review.

## 3. Bounded Contexts Define Scope
A model is consistent within its boundary. Different contexts legitimately model the same concept differently. The boundary is explicit and defended.
**When to apply:** System decomposition, microservice boundaries, team organization.

## 4. Strategy Before Tactics
Getting bounded context boundaries right matters more than getting entities right. Strategic design trumps tactical patterns every time.
**When to apply:** Project kickoff, architecture review, when teams jump to implementation.

## 5. Invest in Core Domain
Distillation: core domain gets the best minds and deepest modeling. Supporting subdomains get simpler treatment. Generic subdomains get bought off the shelf.
**When to apply:** Resource allocation, build-vs-buy, team assignment.

## 6. Protect Model Integrity
Anti-Corruption Layers prevent one context's model from being corrupted by another. Translation at the boundary, not compromise in the model.
**When to apply:** Integration with legacy systems, third-party APIs, cross-team interfaces.
