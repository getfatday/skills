# Gene Kim Anti-Patterns

## Heroics
**Signal:** One person saves the day, works weekends, is the only one who knows the system.
**Kim says:** "Everyone depends on Brent." That person IS the bottleneck.
**Correction:** Spread knowledge. Eliminate single points of failure. No heroes, just systems.

## Invisible Work
**Signal:** No kanban board. No WIP limits. "How long will it take?" "I don't know."
**Kim says:** "Until you make work visible, you can't manage it."
**Correction:** Make ALL work visible. Track the four types. Limit WIP. Measure lead time.

## Manual Deployment
**Signal:** Deployment is a multi-day event requiring a change review board and overtime.
**Kim says:** "If it hurts, do it more frequently."
**Correction:** Deployment pipeline. Automated. From commit to production. Every time.

## Infrequent Releases
**Signal:** Quarterly releases. Big batches. Integration hell. Long stabilization periods.
**Kim says:** Big batches = big risk = big rollbacks. The pain grows exponentially.
**Correction:** Small, frequent releases. Deploy daily or more. Reduce batch size.

## Blame Culture
**Signal:** "Who broke the build?" "Whose fault was the outage?"
**Kim says:** People hide mistakes in blame cultures. No learning happens.
**Correction:** Blameless postmortems. Focus on system causes, not human error.

## Functional Freeze
**Signal:** Can't deploy. Can't change. Everything is entangled. Months of approvals.
**Kim says:** The opposite of locality and simplicity. The organization is wired wrong.
**Correction:** Decompose. Teams own their services end-to-end. Local changes, local deploys.

## Feature Factory
**Signal:** Ship features constantly. Never measure outcomes. Velocity is the only metric.
**Kim says:** The Fifth Ideal is Customer Focus. Measure customer value, not story points.
**Correction:** Outcome metrics. Customer satisfaction. Business impact. Not velocity.
