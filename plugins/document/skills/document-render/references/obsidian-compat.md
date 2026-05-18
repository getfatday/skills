# Obsidian + Dataview Compatibility

`document-render` implements a strict subset of Dataview DQL. Queries
that stay within the subset render identically in both environments,
so consumers can rely on live Obsidian rendering during authoring and
static rendering at publish or CI time.

## What Works in Both

| Construct | Dataview (live) | document-render (static) |
|-----------|-----------------|---------------------------|
| `TABLE` | ✅ | ✅ |
| `TABLE WITHOUT ID` | ✅ | ✅ |
| `FROM "folder"` | ✅ | ✅ |
| `WHERE <expr>` | ✅ | ✅ |
| `SORT <field> [ASC\|DESC]` | ✅ | ✅ |
| `LIMIT N` | ✅ | ✅ |
| `GROUP BY <expr>` | ✅ | ✅ |
| `AS "Label"` | ✅ | ✅ |
| `file.name`, `file.link`, `file.folder` | ✅ | ✅ |
| `file.mtime`, `file.ctime` | ✅ | ✅ (ISO date, not datetime) |
| `contains(a, b)` | ✅ | ✅ |
| `choice(cond, a, b)` | ✅ | ✅ |
| `date(today)` | ✅ | ✅ |
| `length(v)` | ✅ | ✅ |
| `lower(s)`, `upper(s)` | ✅ | ✅ |
| `__count__` / `length(rows)` in grouped queries | ✅ | ✅ |
| Comparison / logical operators | ✅ | ✅ |

## What's Intentionally Left Out

The following Dataview features render live in Obsidian but are NOT in
the portable subset. Avoid them in queries you want to render
statically; if you must use them, wrap them in an
`> [!note]- Obsidian-only` callout so static consumers know to open the
file in Obsidian.

| Construct | Reason |
|-----------|--------|
| `LIST` and `TASK` query types | Not table-shaped; different output model |
| `FLATTEN`, `EXTRACT` | Row-shape transformations would require bigger AST |
| `FROM "A" OR "B"` | Multi-source composition; parser complexity |
| Computed columns referencing other SELECT labels | Requires a second evaluation pass |
| Inline queries (`=dv.pages(...)`) | JS runtime |
| `dataviewjs` fenced blocks | JS runtime |
| `regexmatch`, `striptime`, `dur`, `round`, `sum`, `min`, `max` | Not in the v1 subset |
| `FILE(x)` and other file-coercion helpers | Not needed in the v1 subset |
| Task-specific predicates (`completed`, `fullyCompleted`) | Only relevant for TASK queries |

## Authoring Tips

- **Write queries assuming static rendering.** If you can express your
  query without the unsupported features above, both renderers will
  agree.
- **Use `file.link` for file columns.** Obsidian and
  `document-render` both emit `[[Path|Name]]` — GitHub renders the
  fallback `[[...]]` as plain text but the full wikilink round-trips
  when the file is viewed in Obsidian.
- **Prefer `choice()` over inline conditionals.** Dataview supports
  several syntactic forms; `choice(cond, a, b)` is the most portable.
- **Test both.** Preview the query live in Obsidian, then run
  `/document:render <file> --write-companion` and diff the companion
  against what you saw in Obsidian. If they differ, you're outside the
  portable subset.

## Handling Unsupported Queries

When `document-render` encounters a query it cannot parse or execute,
it replaces the fenced block with an error callout:

```markdown
> [!error] document-render: ParseError: ...
> Source:
> ```
> LIST FROM "Sessions"
> ```
```

This keeps the rest of the document rendering so a single bad query
doesn't nuke the whole file.
