# Root Type Update

The product-portfolio root type's `## Collections` table gains one new row for the program type. Existing rows are unchanged, including the initiatives row. Both registrations are valid.

## Current Collections table (product-portfolio.md)

| Collection | Type | Key | Path |
|------------|------|-----|------|
| brands | brand | name | ./Brands/{name}.md |
| products | product | name | ./Products/{name}/index.md |
| people | person | slug | ./People/{slug}.md |
| initiatives | initiative | title | ./Initiatives/{title}/index.md |
| decisions | decision | title | ./Decisions/{title}.md |
| meeting-notes | meeting-note | date-title | ./Meetings/{date}-{title}.md |
| okrs | okr | quarter-name | ./OKRs/{quarter}-{name}.md |
| constraints | constraint-log | name | ./Constraints/{name}.md |
| customers | customer-profile | category-name | ./Customers/{category}/{name}.md |

## Row to add

| Collection | Type | Key | Path |
|------------|------|-----|------|
| programs | program | name | ./Programs/{name}/index.md |

## Dual hosting: initiatives

The root type already declares initiatives at `./Initiatives/{title}/index.md`. The program type also declares initiatives at `./initiatives/{title}/index.md` (relative to the program directory). Both registrations are valid. The same initiative type definition is reusable across hosts, per the schema principle: "A type can live in multiple places."

During `initiative create`, the generated initiative skill should ask which location to use: standalone (root level) or under a specific program. During `initiative list`, the skill should glob both locations. During `initiative validate`, either location is accepted.

The root-level initiatives row is NOT removed. Standalone initiatives remain valid.

## Dual hosting: epics

Epics are hosted by initiatives (in the initiative type's Collections table) AND directly by programs. When an epic belongs to a program but not a specific initiative, it lives at `./Programs/{name}/epics/{title}.md`. When it belongs to an initiative, it lives under that initiative's directory. Both are valid locations.

## Registration approach

The program type is both standalone (registered in root Collections) AND a parent (hosts initiatives and epics in its own Collections table). These are not mutually exclusive. Step 10 of the define operation handles both: add a row to root Collections for the program itself, and the program's own Collections table declares its children.
