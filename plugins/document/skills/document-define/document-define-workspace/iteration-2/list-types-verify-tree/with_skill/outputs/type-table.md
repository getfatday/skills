# Document Types

16 types defined. 16 skills generated. 0 stale.

| Document Type | Description | Location | Key | Skill | Features |
|---|---|---|---|---|---|
| Product Portfolio | Shared context and perspective engine for Expedia Group | ./index.md | (root) | generated | C |
| Brand | A brand identity within the organization | ./Brands/{name}.md | name | generated | |
| Product | A product hub with PRDs, design briefs, and architecture | ./Products/{name}/index.md | name | generated | C, F |
| Person | A team member or stakeholder across Expedia Group | ./People/{slug}.md | slug | generated | |
| Initiative | A strategic grouping of epics. Maps to PRODPLAN1 in Jira. | ./Initiatives/{title}/index.md | title | generated | C |
| Decision | An architectural or organizational decision record in MADR format | ./Decisions/{title}.md | title | generated | |
| Meeting Note | Notes from a team meeting, sync, or working session | ./Meetings/{date}-{title}.md | date-title | generated | |
| OKR | Quarterly OKRs with paired indicators | ./OKRs/{quarter}-{name}.md | quarter-name | generated | |
| Constraint Log | Tracks THE current system constraint | ./Constraints/{name}.md | name | generated | |
| Customer Profile | A team, brand, or org that consumes products in this portfolio | ./Customers/{category}/{name}.md | category-name | generated | |
| PRD | Product Requirements Document | Products/{name}/prd.md | (facet of product) | generated | H |
| Strategic Context | The six-layer information stack for autonomous decisions | Products/{name}/strategy.md | (facet of product) | generated | H |
| User Story | A user-facing requirement linked to a PRD | Products/{name}/stories/{story-id}.md | story-id | generated | H |
| Opportunity Tree | An Opportunity Solution Tree | Products/{name}/opportunities/{name}.md | name | generated | H |
| Experiment | A Build-Measure-Learn experiment | Products/{name}/experiments/{name}.md | name | generated | H |
| Epic | A large unit of work within an initiative | Initiatives/{title}/epics/{title}.md | title | generated | H |

## Legend

- **C** = has Collections (hosts child types)
- **F** = has Facets (sections extractable to sibling files)
- **H** = Hosted by parent (lives under another type's directory)
