# Root Type Update

The product-portfolio root type's `## Collections` table would gain one new row for the program type.

## Current Collections table (product-portfolio.md)

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

## Row to add

| Collection | Type | Key | Path |
|------------|------|-----|------|
| programs | program | name | ./Programs/{name}/index.md |

## Notes

- The program type uses a directory-based path (`{name}/index.md`) rather than a flat file path because it hosts child collections (initiatives and epics). The child collections live as subdirectories under each program directory.
- Adding program to the root means initiatives and epics are now hosted in TWO places: as standalone collections under the root, AND as child collections under each program. The skill should handle this ambiguity. During `create` for an initiative or epic, it should ask whether the document belongs to a program or is standalone.
- Alternatively, the existing root-level `initiatives` row could be removed if all initiatives must live under a program. This is an architectural decision the user should make.
