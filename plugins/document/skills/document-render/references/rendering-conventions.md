# Rendering Conventions

Shared conventions that both the live Obsidian + Dataview renderer AND
the portable `document-render` script honor. Types that declare
`priority` or `health` fields and templates that want portable rendering
should emit queries that use these helpers. The result: identical
visual output whether the user is viewing inside Obsidian or looking at
a static markdown file on GitHub.

## Priority Glyphs

Priority is a numeric field (0-4). Lower numbers are higher priority.

| Priority | Glyph | Meaning |
|----------|-------|---------|
| 0 | 🔥 | urgent / now |
| 1 | ⚡ | high / this week |
| 2 | • | normal / default |
| 3 | ▾ | low / nice-to-have |
| 4 | ⏸ | paused / on hold |

Canonical `choice()` for a priority column:

```
choice(priority = 0, "🔥",
  choice(priority = 1, "⚡",
  choice(priority = 2, "•",
  choice(priority = 3, "▾",
  choice(priority = 4, "⏸", "•")))))
```

Any document that is missing `priority` gets the default `•` glyph.

## Health Glyphs

Health is an enum field with three values: `on`, `at`, `off`.

| Health | Glyph | Meaning |
|--------|-------|---------|
| `on` | 🟢 | on track |
| `at` | 🟡 | at risk |
| `off` | 🔴 | off track / blocked |

Canonical `choice()`:

```
choice(health = "on", "🟢",
  choice(health = "at", "🟡",
  choice(health = "off", "🔴", "—")))
```

Any document whose `health` field is missing or has an unexpected value
renders as `—`.

## Status Accent (Optional)

For lifecycle status fields, a light accent helps scanning but is not
canonical — types pick their own or skip it. A common default:

```
choice(status = "active", "▶", choice(status = "paused", "⏸", choice(status = "completed", "✓", choice(status = "abandoned", "✗", status))))
```

## Progressive Disclosure

Long tables get wrapped in a collapsible abstract callout so readers see
a preview by default and can expand to see the full list. Use native
GitHub-flavored markdown (no Obsidian-specific syntax):

```markdown
> [!abstract]- Full list (N items)
> ```dataview
> TABLE ... FROM "..." SORT ... LIMIT 50
> ```
```

The top of the document shows a trimmed "top 5" version without the
`-` suffix (which would collapse it):

```markdown
> [!abstract] Top 5
> ```dataview
> TABLE ... FROM "..." SORT ... LIMIT 5
> ```
```

Both the Obsidian callout renderer and plain GitHub markdown handle this
pattern — Obsidian shows the colored banner + collapse chevron; GitHub
shows the blockquote with a styled "abstract" label (via GFM alerts).
`document-render` does NOT rewrite the callout itself; it only
substitutes the inner dataview block.

## Column Helpers

### File name with link

Always emit links via `file.link`, which produces a piped wikilink
`[[Path/To/File|Name]]`. Both Obsidian and the portable renderer output
the same link form.

### Age column

A quick "age in days" column is a common ask. Since DQL doesn't offer
arithmetic on dates in the portable subset, emit `created` as a plain
column and let the reader eyeball it. If a type really needs arithmetic,
the type's `{type}.skill.md` sidecar can declare a templating operation
that computes age at render time (outside the portable DQL subset).

## Default Glyph Fallback

Every `choice()` that maps a value to a glyph should end with a sensible
default — an em dash `—` or the field's raw value — so rows with
missing or unexpected data still render legibly. Never let a `choice()`
fall through to an empty string.

## Design Principles

1. **One visual language.** Both renderers produce the same output.
   Types that need different glyphs per consumer are out of scope for
   the portable subset.
2. **All glyphs are Unicode text.** No SVG, no custom emoji, no images.
   Render identically in terminals, GitHub, Obsidian, and VS Code.
3. **Canonical choice() patterns.** Types and templates lift their
   glyph mappings from this doc verbatim — if you need to change them,
   update this reference first so both renderers stay in lockstep.
4. **Fallbacks are first-class.** Every mapping documents what to render
   when the field is missing or holds an unexpected value.
