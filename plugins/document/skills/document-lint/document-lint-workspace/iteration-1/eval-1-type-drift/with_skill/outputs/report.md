# Document Lint Report: Milestone Map Type Drift

Scoped to: `Strategies/` subtree
Run date: 2026-03-27

## Document Lint Results

### Fixed
- 0 unlinked people references resolved (0 new People files created)
- 0 orphaned documents cataloged in indexes
- 0 documents with missing required sections got TODO stubs

### Needs Review
- 10 documents are mistyped (see below)
- 1 document cluster suggests a new type definition

### Type Drift Candidates

All 10 Milestone Map documents under `Strategies/` are typed as `research` but are clearly not research artifacts. They are Jira-synced milestone inventory tables.

| File | Current Type | Suggested Type | Evidence |
|------|-------------|----------------|----------|
| `Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md` | research | *new: milestone-map* | No `## Findings` section (required for research). Contains `## Active Milestones`, `## Backlog`, `## Draft`, `## Initiatives` with tabular Jira data. `sources: Jira`. |
| `Strategies/Drive EG Advertising Growth/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Tables with columns: Milestone, Jira, Status, Owner, Due. |
| `Strategies/Empower Supply with Agentic AI/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Expand Internationally/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Make Customer Service a Differentiator and Delighter/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Make Hotels.com the Most Rewarding Way to Book a Hotel/Milestone Map.md` | research | *new: milestone-map* | No `## Findings`. Sections organized by Objective with same table columns. `sources: Jira`. |
| `Strategies/Power B2B Enterprise/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Unleash Traveler Marketplace Excellence/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Vrbo is the Trusted Destination for Groups/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |
| `Strategies/Win the Whole Trip on BEX/Milestone Map.md` | research | *new: milestone-map* | Same structure. No `## Findings`. Jira-synced tables. |

### New Type Candidates

| Pattern | Count | Example Files |
|---------|-------|---------------|
| Milestone Map (Jira-synced milestone inventory table) | 10 | `Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md`, `Strategies/Win the Whole Trip on BEX/Milestone Map.md`, `Strategies/Drive EG Advertising Growth/Milestone Map.md` |

---

## Detailed Analysis

### Why these are not `research`

The `research` type (defined in `.config/documents/types/research.md`) requires:
- **Required section:** `## Findings`
- **Purpose:** "Research artifact -- analysis, findings, or investigation that informs product decisions"

None of the 10 Milestone Map files have a `## Findings` section. Their content is purely tabular milestone inventories synced from Jira, not analysis or investigation.

### What they actually are

All 10 files share a consistent structure:
- **Frontmatter:** `type`, `title` ("Milestone Map"), `created`, `author`, `status`, `sources` ("Jira")
- **Opening line:** "Full milestone inventory under [Strategy Name](index.md) (STRAT1-XXXX). Synced from Jira on {date}."
- **Sections:** `## Active Milestones`, `## Backlog`, `## Draft` (optional), `## Initiatives`
- **Table columns:** `| Milestone | Jira | Status | Owner | Due |`
- One variant (`Make Hotels.com...`) organizes by Objective subsections but uses the same table format

No existing type in `.config/documents/types/` matches this structure. The closest is `milestone`, but that describes individual milestones, not a roll-up inventory table.

### Recommended Fixes

#### Step 1: Create a new `milestone-map` type definition

Create `.config/documents/types/milestone-map.md` via `/document:document-define` with:

```markdown
# Milestone Map

## Identity
- name: milestone-map
- display: Milestone Map
- description: Jira-synced inventory of all milestones under a strategy, organized by status. One per strategy.

## Fields

### Required
- `type: string` -- always "milestone-map"
- `title: string` -- always "Milestone Map"
- `created: date` -- date of last sync
- `sources: string` -- always "Jira"

### Optional
- `author: string` -- who ran the sync
- `status: enum(current, stale)` -- whether the data is fresh

## Sections

### Required
- `## Active Milestones` -- table of in-progress milestones

### Optional
- `## Backlog` -- table of backlog milestones
- `## Draft` -- table of draft milestones
- `## Completed` -- table of completed milestones
- `## Initiatives` -- cross-reference to initiative documents

## Table Schema
Each milestone table uses columns: Milestone | Jira | Status | Owner | Due

## Lifecycle
- status-field: status
- values: current, stale
- transitions:
  - current -> stale -- data is more than 7 days old
  - stale -> current -- re-synced from Jira
```

#### Step 2: Retype all 10 documents

For each file, change the frontmatter `type` field from `research` to `milestone-map`.

**Before (all 10 files):**
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

**After:**
```yaml
---
type: milestone-map
title: Milestone Map
created: 2026-03-26
author: ianderson
status: current
sources: Jira
---
```

No other changes needed to the document bodies -- the sections and tables already match the proposed type definition. The `status` field value `current` is valid for both the old research type and the new milestone-map type.

### Files to modify

| Action | File |
|--------|------|
| **Create** | `.config/documents/types/milestone-map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Accelerate Agentic AI for Travelers/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Drive EG Advertising Growth/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Empower Supply with Agentic AI/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Expand Internationally/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Make Customer Service a Differentiator and Delighter/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Make Hotels.com the Most Rewarding Way to Book a Hotel/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Power B2B Enterprise/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Unleash Traveler Marketplace Excellence/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Vrbo is the Trusted Destination for Groups/Milestone Map.md` |
| **Edit** (line 2: `type: research` -> `type: milestone-map`) | `Strategies/Win the Whole Trip on BEX/Milestone Map.md` |
