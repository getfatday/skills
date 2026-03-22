# Observations

## Missing Skills

1. **product-portfolio** has no generated skill at `.claude/skills/product-portfolio/SKILL.md`. All other 15 types have generated skills. This is the root type, so it may be intentional (the root document is managed manually), but the list-types operation flags it as "missing."

## Stale Skills

None. All 15 generated skills have `materialized: "2026-03-21"` and all type definitions were last modified on 2026-03-21. No staleness detected.

## Initiative and Epic Path Ambiguity

The initiative type is declared in root Collections as a flat file: `./Initiatives/{name}.md`. However, initiative also declares a Collections table hosting epics at `./epics/{name}.md` (relative path).

For a flat-file parent, the collection path resolves relative to the parent file's directory, not relative to a parent directory named after the initiative. This means ALL initiatives would share a single `./Initiatives/epics/` directory, which creates a collision risk: two initiatives could both have an epic named the same thing.

Compare with product, which is a directory-based hub (`./Products/{name}/index.md`). Each product gets its own directory, so collections like `./stories/` are naturally scoped per product.

The initiative type would need to either:
- Change its location to a directory hub pattern (`./Initiatives/{name}/index.md`) to scope epics per initiative, or
- Include the initiative slug in the epic path (e.g., `./Initiatives/{name}/epics/{name}.md` at the root level)

## Meeting Note Has No Lifecycle Section

The meeting-note type definition has no `## Lifecycle` section. It defines fields and sections but no status field, no valid statuses, and no transitions. This is not invalid per the schema (Lifecycle is not listed as required), but it means the generated skill's `update-status` operation has nothing to enforce. The skill was still generated.

## Customer Profile Key Ambiguity

The root Collections table declares customer-profile with key `category-name` and path `./Customers/{category}/{name}.md`. The key is a compound of two fields (`category` and `name`), but the key column says `category-name` as a single value. The path uses two separate template variables. This compound key pattern is not documented in the type-definition-schema as a supported key format.

## PRD Dual Hosting Potential

The PRD type appears in product's Facets table (`./prd.md` as a sibling file to the product hub). It does NOT appear in product's Collections table. This means PRD is hosted exclusively as a facet of product. The resolution correctly finds it via Facets.

However, the schema documentation notes: "When a type appears in both a parent's Facets table AND its Collections table, the Facets path takes precedence." This rule is not exercised here since PRD only appears in Facets, not in both.

## No Fallback Resolutions

All 16 types resolved through either root Collections, parent Collections, parent Facets, or root-location. No type required the fallback path (`./{DisplayName}/`). This indicates the tree is fully declared.

## Tree Structure Summary

```
product-portfolio (root)
  +-- brand (root Collection)
  +-- product (root Collection)
  |     +-- prd (Facet)
  |     +-- strategic-context (Facet)
  |     +-- user-story (Collection)
  |     +-- opportunity-tree (Collection)
  |     +-- experiment (Collection)
  +-- person (root Collection)
  +-- initiative (root Collection)
  |     +-- epic (Collection)
  +-- decision (root Collection)
  +-- meeting-note (root Collection)
  +-- okr (root Collection)
  +-- constraint-log (root Collection)
  +-- customer-profile (root Collection)
```

## Consistency Between Root and Child Declarations

All 9 types declared in the root's Collections table have matching type definitions. All child types referenced in product's Collections/Facets and initiative's Collections have matching type definitions. No orphaned references.

No type definition references a child type that lacks a definition. No type definition is unreachable from the root (every type is either in root Collections, or hosted by a type that is in root Collections).
