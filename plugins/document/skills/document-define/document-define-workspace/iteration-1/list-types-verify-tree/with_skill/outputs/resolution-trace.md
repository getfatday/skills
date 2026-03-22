# Location Resolution Trace

For each type, shows how its location was resolved following the algorithm:
root Collections -> parent Collections -> parent Facets -> fallback.

## product-portfolio

- **Resolution method:** root document (`root.md` -> `root-location`)
- **Path:** `./index.md`
- **Source:** `.config/documents/root.md` declares `root-location: ./index.md`
- This is the root type itself. Its location comes from the root document, not from any Collections table.

## brand

- **Resolution method:** root Collections
- **Path:** `./Brands/{name}.md`
- **Source:** `product-portfolio` Collections table, row: `brands | brand | name | ./Brands/{name}.md`

## product

- **Resolution method:** root Collections
- **Path:** `./Products/{name}/index.md`
- **Source:** `product-portfolio` Collections table, row: `products | product | name | ./Products/{name}/index.md`

## prd

- **Resolution method:** parent Facets (product)
- **Path:** `./Products/{product}/prd.md`
- **Source:** `product` type definition Facets table, row: `Product Requirements | ./prd.md | prd`
- Not in root Collections. Not in any parent's Collections. Found in product's Facets table.
- Resolved full path: product location `./Products/{name}/` + facet path `./prd.md` = `./Products/{name}/prd.md`

## user-story

- **Resolution method:** parent Collections (product)
- **Path:** `./Products/{product}/stories/{story-id}.md`
- **Source:** `product` type definition Collections table, row: `stories | user-story | story-id | ./stories/{story-id}.md`
- Not in root Collections. Found in product's Collections table.
- Resolved full path: product location `./Products/{name}/` + collection path `./stories/{story-id}.md` = `./Products/{name}/stories/{story-id}.md`

## strategic-context

- **Resolution method:** parent Facets (product)
- **Path:** `./Products/{product}/strategy.md`
- **Source:** `product` type definition Facets table, row: `Strategy | ./strategy.md | strategic-context`
- Not in root Collections. Not in any parent's Collections. Found in product's Facets table.
- Resolved full path: product location `./Products/{name}/` + facet path `./strategy.md` = `./Products/{name}/strategy.md`

## opportunity-tree

- **Resolution method:** parent Collections (product)
- **Path:** `./Products/{product}/opportunities/{name}.md`
- **Source:** `product` type definition Collections table, row: `opportunities | opportunity-tree | name | ./opportunities/{name}.md`
- Not in root Collections. Found in product's Collections table.
- Resolved full path: product location `./Products/{name}/` + collection path `./opportunities/{name}.md` = `./Products/{name}/opportunities/{name}.md`

## experiment

- **Resolution method:** parent Collections (product)
- **Path:** `./Products/{product}/experiments/{name}.md`
- **Source:** `product` type definition Collections table, row: `experiments | experiment | name | ./experiments/{name}.md`
- Not in root Collections. Found in product's Collections table.
- Resolved full path: product location `./Products/{name}/` + collection path `./experiments/{name}.md` = `./Products/{name}/experiments/{name}.md`

## person

- **Resolution method:** root Collections
- **Path:** `./People/{slug}.md`
- **Source:** `product-portfolio` Collections table, row: `people | person | slug | ./People/{slug}.md`

## initiative

- **Resolution method:** root Collections
- **Path:** `./Initiatives/{name}.md`
- **Source:** `product-portfolio` Collections table, row: `initiatives | initiative | name | ./Initiatives/{name}.md`

## epic

- **Resolution method:** parent Collections (initiative)
- **Path:** `./Initiatives/{initiative}/epics/{name}.md`
- **Source:** `initiative` type definition Collections table, row: `epics | epic | name | ./epics/{name}.md`
- Not in root Collections. Found in initiative's Collections table.
- Resolved full path: initiative location `./Initiatives/{name}.md` is a flat file, not a directory hub. The collection path `./epics/{name}.md` is relative to the parent document's directory. This means epics live at `./Initiatives/epics/{name}.md` (sibling to the initiative file, not nested under it).

## decision

- **Resolution method:** root Collections
- **Path:** `./Decisions/{name}.md`
- **Source:** `product-portfolio` Collections table, row: `decisions | decision | name | ./Decisions/{name}.md`

## meeting-note

- **Resolution method:** root Collections
- **Path:** `./Meetings/{date}-{name}.md`
- **Source:** `product-portfolio` Collections table, row: `meeting-notes | meeting-note | date-name | ./Meetings/{date}-{name}.md`

## okr

- **Resolution method:** root Collections
- **Path:** `./OKRs/{quarter}-{name}.md`
- **Source:** `product-portfolio` Collections table, row: `okrs | okr | quarter-name | ./OKRs/{quarter}-{name}.md`

## constraint-log

- **Resolution method:** root Collections
- **Path:** `./Constraints/{name}.md`
- **Source:** `product-portfolio` Collections table, row: `constraints | constraint-log | name | ./Constraints/{name}.md`

## customer-profile

- **Resolution method:** root Collections
- **Path:** `./Customers/{category}/{name}.md`
- **Source:** `product-portfolio` Collections table, row: `customers | customer-profile | category-name | ./Customers/{category}/{name}.md`
