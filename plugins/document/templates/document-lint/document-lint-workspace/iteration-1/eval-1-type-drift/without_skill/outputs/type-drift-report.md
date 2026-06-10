# Type Drift Report: Milestone Map Documents

## Summary

All 10 Milestone Map documents under `Strategies/` are typed as `research` but contain no research content. They are Jira-synced inventory tables listing milestones by status, owner, and due date. The `research` type requires a `## Findings` section and is defined as "analysis, findings, or investigation that informs product decisions." These documents have none of that -- they are tabular reference data.

## Files With Issues

| # | File | Current Type | Issue |
|---|------|-------------|-------|
| 1 | `Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md` | research | Jira-synced table, not research |
| 2 | `Strategies/Drive EG Advertising Growth/Milestone Map.md` | research | Jira-synced table, not research |
| 3 | `Strategies/Empower Supply with Agentic AI/Milestone Map.md` | research | Jira-synced table, not research |
| 4 | `Strategies/Expand Internationally/Milestone Map.md` | research | Jira-synced table, not research |
| 5 | `Strategies/Make Customer Service a Differentiator and Delighter/Milestone Map.md` | research | Jira-synced table, not research |
| 6 | `Strategies/Make Hotels.com the Most Rewarding Way to Book a Hotel/Milestone Map.md` | research | Jira-synced table, not research |
| 7 | `Strategies/Power B2B Enterprise/Milestone Map.md` | research | Jira-synced table, not research |
| 8 | `Strategies/Unleash Traveler Marketplace Excellence/Milestone Map.md` | research | Jira-synced table, not research |
| 9 | `Strategies/Vrbo is the Trusted Destination for Groups/Milestone Map.md` | research | Jira-synced table, not research |
| 10 | `Strategies/Win the Whole Trip on BEX/Milestone Map.md` | research | Jira-synced table, not research |

## Why This Is Wrong

The `research` type definition (`.config/documents/types/research.md`) specifies:

- **Required section:** `## Findings` -- none of these files have it
- **Purpose:** "analysis, findings, or investigation that informs product decisions"
- **Optional sections:** Methodology, Recommendations, Open Questions -- none present

These Milestone Map files contain:
- A title linking to the parent strategy
- A sync date note ("Synced from Jira on 2026-03-26")
- A markdown table with columns: Milestone, Jira, Status, Owner, Due
- No analysis, no findings, no recommendations

## Recommended Fix

No existing type fits these documents. The closest candidate would be `strategy` (since they are facets of strategy directories), but strategy has required sections (`## Description`) and a different purpose.

**Option A (preferred): Create a new `milestone-map` type** via `/document:document-define`. This type would:
- Live as a facet of `strategy` (sibling to `index.md` in each strategy directory)
- Have `sources: Jira` as a standard field
- Require a table section, not findings
- Support `jira_sync` metadata for automated refresh

**Option B (quick fix): Change type to `strategy`** and treat these as strategy facets. This is imprecise but at least stops them from polluting research queries.

## Before/After Example

**Before** (`Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md`):
```yaml
---
type: research
title: Milestone Map
created: 2026-03-26
author: ianderson
status: current
sources: Jira
---
```

**After (Option A -- new type)**:
```yaml
---
type: milestone-map
title: Milestone Map
created: 2026-03-26
author: ianderson
status: current
sources: Jira
strategy: "[Accelerate Agentic AI for Travelers](index.md)"
---
```

**After (Option B -- retype to strategy)**:
```yaml
---
type: strategy
title: "Accelerate Agentic AI for Travelers: Milestone Map"
date: 2026-03-26
status: active
jira_ticket: STRAT1-1337
---
```

## Note: Initiative Audit Files Are Fine

Five `Initiative Audit.md` files also have `type: research` and `sources: Jira`. These were reviewed and are correctly typed -- they contain `## Findings` sections with actual analysis (scope/coverage mismatches, gap identification, recommendations). They source data from Jira but perform research on top of it.

## Scope of Change

- 10 files need frontmatter `type` field changed
- If Option A: 1 new type definition needed at `.config/documents/types/milestone-map.md`
- If Option A: strategy type definition needs a new facet entry for milestone-map
- No body content changes required -- only frontmatter
