# Root Type Update

The following row would be added to the `## Collections` table in `.config/documents/types/product-portfolio.md`:

## Before (existing table)

| Collection | Type | Key | Path |
|------------|------|-----|------|
| brands | brand | name | ./Brands/{name}.md |
| products | product | name | ./Products/{name}/index.md |
| people | person | slug | ./People/{slug}.md |
| initiatives | initiative | name | ./Initiatives/{name}.md |
| decisions | decision | name | ./Decisions/{name}.md |
| meeting-notes | meeting-note | date-name | ./Meetings/{date}-{name}.md |
| okrs | okr | quarter-name | ./OKRs/{quarter}-{name}.md |
| constraints | constraint-log | name | ./Constraints/{name}.md |
| customers | customer-profile | category-name | ./Customers/{category}/{name}.md |

## New row to append

| Collection | Type | Key | Path |
|------------|------|-----|------|
| team-charters | team-charter | name | ./TeamCharters/{name}.md |

## After (complete table)

| Collection | Type | Key | Path |
|------------|------|-----|------|
| brands | brand | name | ./Brands/{name}.md |
| products | product | name | ./Products/{name}/index.md |
| people | person | slug | ./People/{slug}.md |
| initiatives | initiative | name | ./Initiatives/{name}.md |
| decisions | decision | name | ./Decisions/{name}.md |
| meeting-notes | meeting-note | date-name | ./Meetings/{date}-{name}.md |
| okrs | okr | quarter-name | ./OKRs/{quarter}-{name}.md |
| constraints | constraint-log | name | ./Constraints/{name}.md |
| customers | customer-profile | category-name | ./Customers/{category}/{name}.md |
| team-charters | team-charter | name | ./TeamCharters/{name}.md |

## Notes

- The location path `./TeamCharters/{name}.md` is a standalone flat collection (no subdirectory per document).
- In normal operation, the skill would ask the user "Where should these documents live?" before registering. The path above is a reasonable default using the display name.
- The type definition itself has NO `## Collection` section because it is a standalone type. Location is determined entirely by the root type's Collections table, following the principle: "Type definitions do not declare locations. They describe document shape only. Location flows top-down through the tree."
