# Observations: list-types iteration 2

## Previously Reported Issues: Status

### Issue #2: Initiative path should be directory hub
**Status: FIXED.** Root type Collections table now shows `./Initiatives/{title}/index.md` (directory hub pattern), matching product's `./Products/{name}/index.md` pattern. Initiative also declares its own Collections table (epics), which requires the directory hub structure.

### Issue #3: Key fields should match actual type fields
**Status: PARTIALLY FIXED.** Decision uses `title` (matches field). Initiative uses `title` (matches field). Meeting-note uses `date-title` compound key (matches fields `date` and `title`). However, see new findings below for types where Key column references fields that do not exist in the type definition.

### Issue #5: Customer-profile compound key documented
**Status: FIXED.** The schema's Path Conventions section now documents compound keys: "For compound paths, use hyphenated field names (e.g., `category-name` means fields `category` and `name`)." The customer-profile row uses `category-name` as key with path `./Customers/{category}/{name}.md`, and both `category` and `name` are declared fields in the customer-profile type definition.

### Issue #6: meeting-note should show no Lifecycle
**Status: FIXED.** The meeting-note type definition has no `## Lifecycle` section. It is purely informational with no status transitions.

### Issue #8: Root type (product-portfolio) should have a generated skill
**Status: FIXED.** A generated skill exists at `.claude/skills/product-portfolio/SKILL.md` with `generated-by: document-define`, `generator-version: "1.1"`, and `materialized: "2026-03-21"`.

## New Findings

### Finding #1: Key-to-field mismatches on several types

The Collections Key column references field names that do not exist in the child type's Fields section. These are not blockers (the skill can derive filenames), but they create ambiguity about what value populates the path placeholder.

| Parent | Child Type | Key in Collections | Actual Fields | Issue |
|---|---|---|---|---|
| product-portfolio | person | slug | name, role (no `slug` field) | `slug` is not a declared field. Presumably derived from `name` via kebab-case. |
| product-portfolio | okr | quarter-name | quarter, (no `name` field) | `quarter` exists but `name` does not. OKR has no `name` field. |
| product-portfolio | constraint-log | name | constraint, status, created (no `name` field) | `name` does not exist as a field. |
| product | opportunity-tree | name | product, outcome, status, created, author (no `name` field) | `name` does not exist. Possibly should be `outcome` or a slug derived from it. |
| product | experiment | name | product, hypothesis, status, created, author, outcome, opportunity, prd (no `name` field) | `name` does not exist. Possibly should be `hypothesis` or a slug. |

**Recommendation:** Either add `name` (or `slug`) fields to these types, or update the Key column to reference actual field names.

### Finding #2: No fallback resolution needed

All 16 types resolve their location through the tree (root Collections, parent Collections, or parent Facets). No type falls back to the default `./{DisplayName}/` pattern. This confirms the tree is fully wired.

### Finding #3: Epic is doubly nested

Epic lives at `Initiatives/{title}/epics/{title}.md`, making it the only type that is two levels deep in the hosting tree (root -> initiative -> epic). This works correctly with the resolution algorithm but means epic creation requires knowing both the initiative and the epic title.

### Finding #4: person `slug` key has no corresponding field

The person type uses `slug` as its key in the root Collections table, but the person type definition has no `slug` field. It has `name` (full name) and `aliases` (short names). The slug appears to be a derived value (kebab-case of name), not a frontmatter field. The schema Path Conventions section describes field-based keys but does not address derived keys.

**Recommendation:** Either add a `slug: string` field to person, or document that keys can be derived values (not just frontmatter fields).

### Finding #5: Table completeness

The list-types output includes all 16 types. The Features column correctly shows:
- C (Collections): product-portfolio, product, initiative
- F (Facets): product
- H (Hosted): prd, strategic-context, user-story, opportunity-tree, experiment, epic
- No features: brand, person, decision, meeting-note, okr, constraint-log, customer-profile

Product is the only type with both C and F.
