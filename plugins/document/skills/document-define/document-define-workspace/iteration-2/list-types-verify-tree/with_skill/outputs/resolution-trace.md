# Location Resolution Trace

How each type's location was resolved, following the top-down resolution algorithm:
Root document -> root type Collections -> parent type Collections/Facets.

## Root: product-portfolio

- **Source:** root.md `root-location: ./index.md`
- **Resolution:** Direct from root document configuration. This IS the root type.
- **Result:** `./index.md`

## Root Collections (from product-portfolio.md Collections table)

### brand
- **Source:** product-portfolio Collections row: `brands | brand | name | ./Brands/{name}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `name` (string field in brand type definition)
- **Result:** `./Brands/{name}.md`

### product
- **Source:** product-portfolio Collections row: `products | product | name | ./Products/{name}/index.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `name` (string field in product type definition)
- **Result:** `./Products/{name}/index.md` (directory hub)

### person
- **Source:** product-portfolio Collections row: `people | person | slug | ./People/{slug}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `slug` -- note: person type has no `slug` field in Fields section. The key `slug` is derived from the `name` field by convention (kebab-case transform).
- **Result:** `./People/{slug}.md`

### initiative
- **Source:** product-portfolio Collections row: `initiatives | initiative | title | ./Initiatives/{title}/index.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `title` (string field in initiative type definition)
- **Result:** `./Initiatives/{title}/index.md` (directory hub)

### decision
- **Source:** product-portfolio Collections row: `decisions | decision | title | ./Decisions/{title}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `title` (string field in decision type definition)
- **Result:** `./Decisions/{title}.md`

### meeting-note
- **Source:** product-portfolio Collections row: `meeting-notes | meeting-note | date-title | ./Meetings/{date}-{title}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `date-title` (compound key from `date` and `title` fields in meeting-note type definition)
- **Result:** `./Meetings/{date}-{title}.md`

### okr
- **Source:** product-portfolio Collections row: `okrs | okr | quarter-name | ./OKRs/{quarter}-{name}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `quarter-name` (compound key from `quarter` and `name` fields -- note: okr type has no `name` field; the key part `name` may need to be derived or the OKR type may need a `name` field added)
- **Result:** `./OKRs/{quarter}-{name}.md`

### constraint-log
- **Source:** product-portfolio Collections row: `constraints | constraint-log | name | ./Constraints/{name}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `name` -- note: constraint-log type has no `name` field in its Fields section. The key `name` is not directly mappable to a declared field. The type has `constraint` (string) but not `name`.
- **Result:** `./Constraints/{name}.md`

### customer-profile
- **Source:** product-portfolio Collections row: `customers | customer-profile | category-name | ./Customers/{category}/{name}.md`
- **Resolution:** Direct match in root type Collections table.
- **Key field:** `category-name` (compound key from `category` enum field and `name` string field in customer-profile type definition). Per schema Path Conventions: "For compound paths, use hyphenated field names (e.g., `category-name` means fields `category` and `name`)."
- **Result:** `./Customers/{category}/{name}.md`

## Parent-Hosted: Product Collections (from product.md Collections table)

### user-story
- **Source:** product.md Collections row: `stories | user-story | story-id | ./stories/{story-id}.md`
- **Resolution:** Not in root Collections. Found in product type's Collections table.
- **Key field:** `story-id` (string field in user-story type definition)
- **Result:** `Products/{product-name}/stories/{story-id}.md`

### opportunity-tree
- **Source:** product.md Collections row: `opportunities | opportunity-tree | name | ./opportunities/{name}.md`
- **Resolution:** Not in root Collections. Found in product type's Collections table.
- **Key field:** `name` -- note: opportunity-tree type has no `name` field. It has `outcome` (string). The key `name` may need to map to a different field or the type may need a `name` field.
- **Result:** `Products/{product-name}/opportunities/{name}.md`

### experiment
- **Source:** product.md Collections row: `experiments | experiment | name | ./experiments/{name}.md`
- **Resolution:** Not in root Collections. Found in product type's Collections table.
- **Key field:** `name` -- note: experiment type has no `name` field. The key `name` is not directly mappable. The type has `hypothesis` (string) but not `name`.
- **Result:** `Products/{product-name}/experiments/{name}.md`

## Parent-Hosted: Product Facets (from product.md Facets table)

### prd
- **Source:** product.md Facets row: `Product Requirements | ./prd.md | prd`
- **Resolution:** Not in root Collections. Found in product type's Facets table.
- **Result:** `Products/{product-name}/prd.md` (sibling of product hub)

### strategic-context
- **Source:** product.md Facets row: `Strategy | ./strategy.md | strategic-context`
- **Resolution:** Not in root Collections. Found in product type's Facets table.
- **Result:** `Products/{product-name}/strategy.md` (sibling of product hub)

## Parent-Hosted: Initiative Collections (from initiative.md Collections table)

### epic
- **Source:** initiative.md Collections row: `epics | epic | title | ./epics/{title}.md`
- **Resolution:** Not in root Collections. Not in product Collections/Facets. Found in initiative type's Collections table.
- **Key field:** `title` (string field in epic type definition)
- **Result:** `Initiatives/{initiative-title}/epics/{title}.md`

## Summary

- **9 types** resolved from root type Collections table (no fallback needed)
- **5 types** resolved from product type's Collections or Facets tables (no fallback needed)
- **1 type** resolved from initiative type's Collections table (no fallback needed)
- **1 type** (product-portfolio) resolved from root-location in root.md
- **0 types** required fallback resolution
