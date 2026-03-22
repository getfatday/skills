# Document Types

16 types defined. 15 skills generated. 0 stale.

| Document Type | Description | Location | Skill | Features | Status |
|---|---|---|---|---|---|
| Product Portfolio | Shared context and perspective engine for Expedia Group | ./index.md | missing | C | enabled |
| Brand | A brand identity within the organization | ./Brands/{name}.md | generated | -- | enabled |
| Product | A product hub with PRDs, design briefs, and architecture | ./Products/{name}/index.md | generated | C, F | enabled |
| PRD | Product Requirements Document | ./Products/{name}/prd.md | generated | H | enabled |
| User Story | A user-facing requirement linked to a PRD | ./Products/{name}/stories/{story-id}.md | generated | H | enabled |
| Strategic Context | The six-layer information stack that empowered teams need to make autonomous decisions | ./Products/{name}/strategy.md | generated | H | enabled |
| Opportunity Tree | An Opportunity Solution Tree linking desired outcomes to customer opportunities, candidate solutions, and assumption tests | ./Products/{name}/opportunities/{name}.md | generated | H | enabled |
| Experiment | A Build-Measure-Learn experiment with hypothesis, MVP, pre-defined success criteria, and validated learning | ./Products/{name}/experiments/{name}.md | generated | H | enabled |
| Person | A team member or stakeholder across Expedia Group | ./People/{slug}.md | generated | -- | enabled |
| Initiative | A strategic grouping of epics. Maps to PRODPLAN1 in Jira. | ./Initiatives/{name}.md | generated | C | enabled |
| Epic | A large unit of work within an initiative | ./Initiatives/{name}/epics/{name}.md | generated | H | enabled |
| Decision | An architectural or organizational decision record in MADR format | ./Decisions/{name}.md | generated | -- | enabled |
| Meeting Note | Notes from a team meeting, sync, or working session | ./Meetings/{date}-{name}.md | generated | -- | enabled |
| OKR | Quarterly OKRs with paired indicators (every quantity metric has a quality counterpart) | ./OKRs/{quarter}-{name}.md | generated | -- | enabled |
| Constraint Log | Tracks THE current system constraint, its exploitation, and the improvement cycle | ./Constraints/{name}.md | generated | -- | enabled |
| Customer Profile | A team, brand, or org that consumes products in this portfolio | ./Customers/{category}/{name}.md | generated | -- | enabled |

**Legend:** C = has Collections, F = has Facets, H = hosted by parent type
