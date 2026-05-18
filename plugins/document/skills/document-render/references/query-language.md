# Query Language — Supported DQL Subset

`document-render` executes a strict subset of the Dataview Query
Language (DQL). Queries that stay within this subset render identically
under live Obsidian + Dataview AND under the portable Python renderer.
Anything outside this subset is not guaranteed to render in both
environments.

## Query Shape

```
TABLE [WITHOUT ID] <column_list>
FROM "<folder>"
WHERE <expr>
SORT <expr> [ASC|DESC]
LIMIT <number>
GROUP BY <expr>
```

All clauses after `TABLE` are optional. Order is fixed: `FROM`,
`WHERE`, `SORT`, `LIMIT`, `GROUP BY`.

### TABLE / TABLE WITHOUT ID

`TABLE WITHOUT ID` suppresses the default first column (the linked
file). Use it when your SELECT list already has the columns you want.

```
TABLE WITHOUT ID file.link AS "Session", status, created
```

The column list is comma-separated. Each column is either an
expression or an expression followed by `AS "Label"`. Unlabeled
columns use the expression text as the header.

### FROM "folder"

Restricts the query to files under `<portfolio-root>/folder/`. The
quoted string is a folder path relative to the portfolio root. Omit
the clause to scan the entire portfolio (skipping `.config/`,
`.claude/`, `scripts/`, `docs/`, `.git/`).

Currently only a single quoted folder is supported. Logical operators
over FROM sources (e.g., `FROM "A" OR "B"`) are NOT supported.

### WHERE expression

A boolean expression that filters files. Supported operators:

| Operator | Meaning |
|----------|---------|
| `=`, `!=` | equality / inequality (string or numeric) |
| `<`, `<=`, `>`, `>=` | comparison (numeric if both coerce; lexicographic otherwise) |
| `AND`, `OR`, `NOT` | boolean combinators |

Parentheses `( ... )` group subexpressions.

### SORT expression [ASC|DESC]

Sorts the filtered rows by the expression. Default is `ASC`.

```
SORT created DESC
SORT priority ASC
SORT file.name
```

Inside a `GROUP BY` query, `SORT __count__` and `SORT __group__` are
supported for sorting by the number of members in each group or by
the group key itself.

### LIMIT N

Truncates the result set to the first N rows (after sort).

### GROUP BY expression

Buckets rows by the expression's value. Each bucket becomes one row.
The group key is emitted as the first column automatically.

Inside a grouped query, use `__count__` in SELECT or SORT to reference
the number of members in each group (Dataview's `length(rows)` is an
equivalent alias).

## Expressions

### Identifiers

| Identifier | Resolves to |
|------------|-------------|
| `<field>` | Frontmatter value for that key (case-insensitive fallback) |
| `file.name` | File stem, or parent dir name for `index.md` files |
| `file.folder` | Parent directory path relative to portfolio root |
| `file.link` | Wikilink to the file, piped with display name |
| `file.mtime` | ISO date of last modification |
| `file.ctime` | ISO date of creation |

### Literals

- String: `"foo"`
- Number: `42`, `3.14`, `-7`

### Functions

| Function | Signature | Behavior |
|----------|-----------|----------|
| `contains(haystack, needle)` | 2 args | substring-or-list membership (case-insensitive for strings) |
| `choice(cond, if_true, if_false)` | 3 args | ternary |
| `date(today)` | 1 arg | today's date, ISO (only `today` is supported) |
| `length(v)` | 1 arg | string length or list length |
| `lower(s)` | 1 arg | lowercase |
| `upper(s)` | 1 arg | uppercase |

Functions are case-insensitive. Calls nest.

### Truthiness

A value is falsy if it's `null`, `""`, `0`, `False`, or an empty list.
All other values are truthy. Used by `NOT` and `choice()`.

## Examples

### Active sessions, newest first

```dataview
TABLE WITHOUT ID file.link AS "Session", project, status
FROM "Sessions"
WHERE status = "active"
SORT created DESC
LIMIT 10
```

### Health glyphs via choice()

```dataview
TABLE WITHOUT ID file.link AS "Project",
  choice(health = "on", "🟢", choice(health = "at", "🟡", "🔴")) AS "Health",
  status
FROM "Projects"
```

### Count by status

```dataview
TABLE WITHOUT ID __count__ AS "Count"
FROM "Sessions"
GROUP BY status
SORT __count__ DESC
```

### Workstreams I can resume

```dataview
TABLE WITHOUT ID file.link AS "Workstream", closed, workstream-next-action AS "Next Action"
FROM "Sessions"
WHERE workstream-status = "paused" OR (workstream-status = "active" AND status = "paused")
SORT closed DESC
LIMIT 10
```

## Not Yet Supported (planned Phase 8d+)

These render fine under live Dataview but not yet under
`document-render`. Avoid them in portable queries:

- `LIST` or `TASK` query types (only `TABLE` is supported)
- `FLATTEN` / `EXTRACT` clauses
- Nested `FROM` via logical operators on sources (`FROM "A" OR "B"`)
- Computed columns that reference other SELECT column labels
- `regexmatch(...)`, `striptime(...)`, and other Dataview built-ins
  beyond the table above
- Inline Dataview queries (`=dv.pages(...)`)
- Dataview JS blocks (`dataviewjs`)

If a query uses an unsupported construct, `document-render` emits an
error callout inside the block and continues with the rest of the
document.
