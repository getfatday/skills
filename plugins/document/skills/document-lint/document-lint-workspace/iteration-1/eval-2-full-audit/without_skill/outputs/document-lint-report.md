# Document Lint Report

**Portfolio:** /Users/ianderson/src/product-portfolio
**Date:** 2026-03-27
**Scope:** All content files in People/, Strategies/, Functional Areas/, Decisions/, Plans/, Research/

## Summary

| Check | Issues Found |
|-------|-------------|
| Type-content mismatches | 31 |
| Plain-text people references | 298 |
| Orphaned files (not in any index) | 1,091 of 1,141 |
| Broken markdown links | 55 |
| Oversized index files (>30 lines) | 28 |
| Missing Initiatives/index.md | 166 |

**Total content files:** 1,141 (non-index) + 956 index.md files
**Type distribution (non-index):** initiative (1,055), branch-step (42), research (27), person (6), decision (5), design-brief (3), one-pager (1), opportunity-tree (1), prd (1)

---

## 1. Type-Content Mismatches

### 1a. Wrong type for content (10 files)

Ten "Milestone Map" files are typed `research` but contain milestone inventory tables synced from Jira. They have no `## Findings` section (required for research type). These are reference documents, not research artifacts.

**Files:**
- `Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md`
- `Strategies/Drive EG Advertising Growth/Milestone Map.md`
- `Strategies/Empower Supply with Agentic AI/Milestone Map.md`
- `Strategies/Expand Internationally/Milestone Map.md`
- `Strategies/Make Customer Service a Differentiator and Delighter/Milestone Map.md`
- `Strategies/Make Hotels.com the Most Rewarding Way to Book a Hotel/Milestone Map.md`
- `Strategies/Power B2B Enterprise/Milestone Map.md`
- `Strategies/Unleash Traveler Marketplace Excellence/Milestone Map.md`
- `Strategies/Vrbo is the Trusted Destination for Groups/Milestone Map.md`
- `Strategies/Win the Whole Trip on BEX/Milestone Map.md`

**Before:**
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

**Recommendation:** Either create a dedicated `milestone-map` type or reclassify as an untyped reference artifact (infrastructure). These are generated Jira inventories, not research with findings.

### 1b. Mistyped research file (1 file)

`Functional Areas/HCOM/Products/Differentiated VR on HCOM/Outreach Drafts.md` is typed `research` but contains draft Slack messages for stakeholder outreach. It has no `## Findings` section. This is a communication artifact, not research.

**Before:**
```yaml
---
type: research
title: Dependency Outreach Drafts
created: 2026-03-24
author: Lucy Meadow
status: draft
---
```

**Recommendation:** Remove the type field entirely (making it infrastructure/scratch) or create a type that fits communication drafts.

### 1c. Missing required sections (20 instances across 7 files)

| File | Type | Missing Sections |
|------|------|-----------------|
| `Functional Areas/HCOM/.../Design Brief.md` | design-brief | `## Problem Statement`, `## Context` |
| `Functional Areas/HCOM/.../Design Brief Wave 2.md` | design-brief | `## Problem Statement`, `## Context` |
| `Functional Areas/HCOM/.../Design Brief Wave 3.md` | design-brief | `## Problem Statement`, `## Context` |
| `Functional Areas/HCOM/.../PRD.md` | prd | `## Problem Statement`, `## Context`, `## Desired Outcome`, `## Success Metrics` |
| 10 research files under `...Product Portfolio/Research/` | research | `## Findings` |

Note: The design briefs have the correct structural sections (`## Design Principles`, `## Conceptual Model`, `## User Flows`) but are missing the `## Problem Statement` and `## Context` sections that the type definition lists as required. The type definition may need updating, or the design briefs need these sections added.

The PRD uses `## Executive Summary`, `## Product Context`, `## Discovery Evidence` instead of the required `## Problem Statement`, `## Context`, `## Desired Outcome`, `## Success Metrics`. This is a type-content structure mismatch where the document predates the type definition.

**Before (PRD sections):**
```markdown
## Executive Summary
## Product Context
## Discovery Evidence
## Outcomes & Success Criteria
```

**After (matching prd type):**
```markdown
## Problem Statement
## Context
## Desired Outcome
## Success Metrics
```

---

## 2. Plain-Text People References

**Total:** 298 plain-text people references that should be markdown links.

Per CLAUDE.md: "Cross-references in frontmatter use markdown link syntax: `brand: '[Hotels.com](../Brands/hcom.md)'`. Not plain strings."

### Breakdown by field

| Field | Count |
|-------|-------|
| `assignee` | 276 |
| `author` | 13 |
| `owner` | 3 |
| `lead` | 3 |
| `deciders` | 3 |

### 2a. Assignee fields (276 — bulk of the issue)

All from Jira-synced initiative files under `Strategies/`. These were imported with plain-text assignee names that don't have corresponding People/ files.

**Before:**
```yaml
assignee: "Shrey Panda"
```

**After (if person file exists):**
```yaml
assignee: "[Shrey Panda](../../../../../../../../People/spanda.md)"
```

**After (if no person file):**
```yaml
assignee: "Shrey Panda"
```

Note: Most assignees (276) are people who don't have files in `People/`. Only 6 people files exist (cbates, dstrugnell, ianderson, joschmidt, jotanner, lmeadow). Converting these to links requires either creating People/ files for each person or accepting plain text for people outside the portfolio's scope.

### 2b. Author/owner/lead fields (19 — hand-authored files)

These reference known people who DO have People/ files.

| File | Field | Current Value | Should Be |
|------|-------|--------------|-----------|
| `Research/HCOM HBT Cross-Milestone Dependency Analysis.md` | author | `lmeadow` | `"[Lucy Meadow](../People/lmeadow.md)"` |
| `Functional Areas/Experience Platform/Products/xp-skills/index.md` | owner | `Ian Anderson` | `"[Ian Anderson](../../../../People/ianderson.md)"` |
| `Functional Areas/Experience Platform/index.md` | lead | `Ed Hodges` | plain text OK (no People/ file) |
| `Functional Areas/.../Product Portfolio/index.md` | owner | `Ian Anderson` | `"[Ian Anderson](../../../../../People/ianderson.md)"` |
| `Functional Areas/.../Brand Catalog/opportunities/Brand Asset Fragmentation.md` | author | `Joonas Tanner` | `"[Joonas Tanner](../../../../../People/jotanner.md)"` |
| `Functional Areas/.../Brand Catalog/one-pager.md` | author | `Joonas Tanner` | `"[Joonas Tanner](../../../../People/jotanner.md)"` |
| `Functional Areas/.../Brand Catalog/index.md` | owner | `Joonas Tanner` | `"[Joonas Tanner](../../../../People/jotanner.md)"` |
| `Functional Areas/.../Design System/index.md` | lead | `ianderson` | `"[Ian Anderson](../../../People/ianderson.md)"` |
| `Functional Areas/HCOM/.../Outreach Drafts.md` | author | `Lucy Meadow` | `"[Lucy Meadow](../../../../People/lmeadow.md)"` |
| `Functional Areas/HCOM/.../PRD.md` | author | `"Lucy Meadow"` | `"[Lucy Meadow](../../../../People/lmeadow.md)"` |
| `Functional Areas/HCOM/.../Design Brief.md` | author | `Lucy Meadow` | `"[Lucy Meadow](../../../../People/lmeadow.md)"` |
| `Functional Areas/HCOM/.../Design Brief Wave 2.md` | author | `Lucy Meadow` | `"[Lucy Meadow](../../../../People/lmeadow.md)"` |
| `Functional Areas/HCOM/.../Design Brief Wave 3.md` | author | `Lucy Meadow` | `"[Lucy Meadow](../../../../People/lmeadow.md)"` |
| `Functional Areas/HCOM/.../Decisions/VR Visibility Strategy.md` | deciders | `Lucy Meadow, Evano Pescatore, Jonathan Hooper-Saunders` | needs link for Lucy; others have no People/ file |
| `Functional Areas/HCOM/.../Decisions/MVP Data and Scope Boundaries.md` | deciders | (same as above) | (same) |
| `Functional Areas/HCOM/.../Decisions/Visual Differentiation Approach.md` | deciders | (same as above) | (same) |
| `Functional Areas/HCOM/.../index.md` | lead | `lmeadow` | `"[Lucy Meadow](../../../People/lmeadow.md)"` |
| `Strategies/Empower Supply with Agentic AI/Milestone Map.md` | author | `ianderson` | `"[Ian Anderson](../../People/ianderson.md)"` |

### 2c. Inconsistent name formats

People are referenced using different formats across the portfolio:
- userid only: `ianderson`, `lmeadow`
- Full name: `Ian Anderson`, `Lucy Meadow`, `Joonas Tanner`
- Quoted full name: `"Lucy Meadow"`

The convention should be consistent. Recommendation: always use markdown link syntax with full display name, e.g., `"[Lucy Meadow](../People/lmeadow.md)"`.

---

## 3. Orphaned Files

**Total:** 1,091 of 1,141 non-index content files are not referenced from any index.md.

### By top-level directory

| Directory | Orphans |
|-----------|---------|
| Strategies/ | 1,070 |
| Functional Areas/ | 17 |
| Plans/ | 3 |
| Research/ | 1 |

### 3a. Strategies/ orphans (1,070) — systemic issue

The vast majority are **initiative files** under `Strategies/.../Initiatives/` directories. The root cause is that **166 Initiatives/ directories have no index.md file**. When a Jira sync creates initiative files inside a milestone's Initiatives/ folder but does not generate an index.md for that folder, all initiatives become orphans.

Additionally, milestone index files do not link down to their Initiatives/ subdirectory. The milestone `index.md` only links up to its parent objective, not down to its children.

**Before (milestone index.md):**
```markdown
# Pilot autonomous supply across 5 software systems to add 15k-45k hotels

## Overview

Milestone under [Accelerate Supply Acquisition](../../index.md). Synced from Jira on 2026-03-26.
```

**After (with Initiatives link):**
```markdown
# Pilot autonomous supply across 5 software systems to add 15k-45k hotels

## Overview

Milestone under [Accelerate Supply Acquisition](../../index.md). Synced from Jira on 2026-03-26.

## Initiatives

- [Initiatives](Initiatives/) — 48 initiatives under this milestone
```

### 3b. Functional Areas/ orphans (17)

Hand-authored files under `Functional Areas/` that exist alongside or within products but are not linked from any index.md.

**Files include:**
- 10 research files under `...Product Portfolio/Research/`
- 4 HCOM product files (Design Briefs, PRD, Outreach Drafts)
- 3 HCOM decision files
- Brand Catalog one-pager and opportunity tree

### 3c. Plans/ orphans (3)

Step files in `Plans/remove-okrs-reframe-plans/Steps/` that are not linked from the plan's index.md.

### 3d. Research/ orphan (1)

`Research/HCOM HBT Cross-Milestone Dependency Analysis.md` is not linked from any index.

---

## 4. Broken Links

**Total:** 55 broken markdown links.

### 4a. Parent reference failures (39)

Milestone index files linking `../../index.md` to reach their parent objective. These fail because the milestone directory name contains a **forward slash** (from the Jira title) which splits into nested directories, making the relative path wrong.

**Example:** The Jira title "BEX Japan: Improve Site/App Performance" creates the path:
```
Milestones/BEX Japan: Improve Site/App Performance/index.md
```
Which the filesystem interprets as:
```
Milestones/BEX Japan: Improve Site/
  App Performance/
    index.md
```
So `../../index.md` resolves to `Milestones/index.md` (wrong) instead of the objective's `index.md`.

**Affected patterns:** Directory names containing `/` (from Jira titles), e.g.:
- `BEX KSA/UAE: Launch Cars and Activties`
- `BEX Japan: Improve Site/App Performance`
- `Create lodging waiver request self-service experience for web/app`

**Recommendation:** Sanitize Jira titles during sync by replacing `/` with `-` or `_` in directory names.

### 4b. Missing target files (15)

Links pointing to files that don't exist:
- `Plans/plan-branch-redesign/index.md` references `.config/documents/types/branch.md` and `.config/documents/types/product.md` using relative paths that don't resolve from the plan's location
- Several `Teams/index.md` files have broken links where parentheses in team names broke the markdown link syntax, e.g., `Analyst Tools (Case Management` is a truncated link target
- `Plans/plan-branch-redesign/index.md` links to `~/src/expedia` (tilde path, not valid in markdown)

### 4c. Broken link examples with fixes

**Before (relative path from plan):**
```markdown
[branch type](.config/documents/types/branch.md)
```

**After (correct relative path):**
```markdown
[branch type](../../.config/documents/types/branch.md)
```

**Before (tilde path):**
```markdown
[expedia repo](~/src/expedia)
```

**After (remove or use absolute):**
```markdown
_Local path: ~/src/expedia_
```

**Before (truncated team name in link):**
```markdown
- [Analyst Tools (Case Management](Analyst Tools (Case Management/index.md)
```

**After (escaped parens or simplified):**
```markdown
- [Analyst Tools - Case Management](Analyst%20Tools%20%28Case%20Management%29/index.md)
```

---

## 5. Oversized Index Files

**Convention:** index.md files should be maps (under 30 lines), not content.

**Total:** 28 index files exceed 30 lines.

| Lines | File |
|-------|------|
| 107 | `Strategies/...HCOM.../Deliver for Flexibility and Stickiness/index.md` |
| 94 | `Strategies/...HCOM.../Redesign Hotels.comCash Loyalty Program/index.md` |
| 87 | `Strategies/...HCOM.../Integrate Add-On Services/index.md` |
| 79 | `Strategies/...HCOM.../Build Self Booker Extended Experience/index.md` |
| 76 | `Functional Areas/index.md` |
| 72 | `Strategies/...HCOM.../Create Travel Arranger Persona MLP/index.md` |

Most oversized indexes are milestone hubs under the HCOM strategy that contain inline initiative lists rather than linking to a separate Initiatives/ directory. `Functional Areas/index.md` at 76 lines is the largest non-strategy index, listing all 44 functional areas.

---

## 6. Additional Findings

### 6a. Missing type definitions in use

Files use `type: milestone` (625), `type: objective` (41), `type: functional-team` (172), `type: functional-area` (44), `type: index` (49), `type: strategy` (10), `type: plan` (4), `type: product` (4), `type: branch` (2). Type definitions exist for all of these in `.config/documents/types/`.

### 6b. Jira sync artifacts

The Strategies/ tree (1,055 initiatives + 625 milestones + 41 objectives + 10 strategies) is almost entirely Jira-synced content. The sync creates files with correct types and frontmatter but:
1. Does not create `Initiatives/index.md` files (166 missing)
2. Does not sanitize `/` from Jira titles used as directory names
3. Uses plain-text assignee names without People/ links
4. Truncates long titles with `...` in directory names (228 directories)

### 6c. Directory name issues

228 directories under Strategies/ have names truncated with `...` (from Jira title length limits). These create awkward paths and make navigation difficult.

---

## Priority Recommendations

1. **Generate missing Initiatives/index.md files** (fixes 1,070 orphans) — highest impact, single batch operation
2. **Add downward links in milestone index files** to their Initiatives/ directories
3. **Sanitize Jira titles** during sync: replace `/` with `-`, don't truncate with `...`
4. **Convert 19 hand-authored people references** to markdown link syntax (quick manual fix)
5. **Add `## Findings` sections** to the 10 Product Portfolio research files or reclassify them
6. **Retype Milestone Map files** from `research` to a dedicated type or infrastructure
7. **Fix 15 genuinely broken links** (wrong relative paths, truncated targets)
8. **Split oversized milestone indexes** that embed initiative lists inline
