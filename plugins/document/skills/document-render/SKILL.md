---
name: document-render
description: >
  This skill should be used whenever the user wants to execute
  Dataview DQL queries against markdown frontmatter without Obsidian
  running, or pre-render a markdown file that contains dataview code
  blocks into static markdown tables. Trigger liberally for:
  pre-building GitHub-rendered dashboards from an Obsidian portfolio,
  materializing dataview blocks in CI pipelines, converting vault
  reports to static snapshots for board meetings or external readers,
  running TABLE queries from a shell script, rendering Views/ files to
  .rendered.md companions, or any request to "make these dataview
  blocks actually render as tables on GitHub". Typical phrasings
  include "render the dashboard", "static build of Dashboard.md",
  "pre-render these dataview queries", "my GitHub readme has dataview
  blocks that don't render", "I'm not running Obsidian — how do I
  execute this query?", "build a snapshot of the vault reports for a
  demo", or invoking /document:render directly. Supports a subset of
  DQL (TABLE / FROM / WHERE / SORT / LIMIT / GROUP BY / choice() /
  contains()); unsupported features render as error callouts. Do not
  use for defining new document types, linting, or verifying inferred
  markers. Use whenever the user needs dataview queries to work
  outside Obsidian.
materialized: "2026-04-18"
user-invocable: true
trigger-phrases:
  - "render the document"
  - "document-render"
  - "materialize dataview"
  - "static dataview"
  - "run dataview queries"
allowed-tools: [Read, Write, Bash, Glob, Grep]
---

# document-render

<objective>
Consume a markdown file that contains ` ```dataview ` code blocks, run
each block's query against frontmatter across the portfolio, and emit a
rendered markdown document where each block has been replaced by a
Markdown table. The renderer is `scripts/render.py` — pure Python,
stdlib-only, no Obsidian required.

The query syntax is a strict subset of Dataview DQL (see
`references/query-language.md`). Anything rendered by this skill also
renders live under Obsidian + Dataview; that guarantees the canonical
form works in both environments.
</objective>

## When to Run

- Generating static reports outside Obsidian (e.g., pushing a
  GitHub-rendered dashboard from `~/src/product-portfolio`)
- CI steps that build a materialized view of the portfolio
- Users who want a portable snapshot that won't change as frontmatter
  evolves
- Previewing rendered output before committing

## Operations

### render — Materialize a document

**Inputs:**

- `file` (positional) — path to a markdown file with `dataview`
  code blocks
- `--portfolio <path>` — portfolio root (optional; defaults to
  searching upward for `.config/documents/root.md`)
- `--write-companion` — write `{file}.rendered.md` alongside the
  original (safe, non-destructive default mode for first use)
- `--rewrite-inline` — overwrite the original file in place (use with
  care; pair with git)
- No output flag — print the rendered file to stdout

**Steps:**

1. **Locate the portfolio root.** Walk upward from the input file
   until `.config/documents/root.md` is found. Fail with a clear
   message if none exists.
2. **Read the input file.**
3. **For each ` ```dataview ` fenced block**, parse the body as a DQL
   query (see `references/query-language.md` for the supported
   surface). Errors inside a block render as `> [!error]` callouts so
   the user sees the source query and the failure; they don't abort
   the whole document.
4. **Execute each query.** For each matched frontmatter record,
   evaluate SELECT expressions against the record's fields and the
   `file.*` pseudo-fields (`file.name`, `file.link`, `file.folder`,
   `file.mtime`, `file.ctime`).
5. **Format each result as a GitHub-flavored markdown table.**
6. **Write output.** Based on the chosen mode:
   - `--write-companion` → `{basename}.rendered.md`
   - `--rewrite-inline` → overwrite input
   - Otherwise → stdout

### render-folder — (Coming later) Render every file in a folder

Not yet shipped. Tracked for Phase 8d+. For now, loop over files in the
shell:

```bash
for f in Views/*.md; do
  /document:render "$f" --write-companion
done
```

## Integration with Obsidian (Live)

The queries materialized by this skill are valid Dataview. Obsidian
users don't need to run `document-render` — Dataview renders the same
queries live. See `references/obsidian-compat.md` for the full list of
supported DQL constructs and a few Dataview features intentionally NOT
in the portable subset.

## Glyph and Progressive-Disclosure Conventions

Priority and health fields map to glyphs via `choice()` calls in DQL.
The canonical mappings are documented in
`references/rendering-conventions.md`. Both the live Obsidian renderer
and this skill's static renderer honor the mapping — so `choice(health
= "on", "🟢", choice(health = "at", "🟡", "🔴"))` produces the same
output in either environment.

Progressive disclosure of long tables uses `> [!abstract]-` collapsible
callouts (native GitHub-flavored markdown). The renderer preserves
these blocks verbatim; the tables inside them get substituted just
like top-level blocks.

## Design Principles

1. **Zero Obsidian dependency.** Pure Python stdlib. Runs from any
   shell.
2. **Dataview-compatible.** Every supported construct renders the same
   under live Obsidian. This skill is a portable alternative, not a
   competing language.
3. **Fail inside the block, not the document.** An invalid query
   renders as an error callout. The rest of the document keeps
   rendering.
4. **Safe by default.** Default mode is `--write-companion`; inline
   rewrite requires an explicit flag.
5. **Type-agnostic.** The renderer reads any frontmatter field. It has
   no idea what `session` or `epic` means — it just queries markdown
   records. Convention (not code) gives meaning.

<dependencies>
reads_from:
  - .config/documents/root.md (to locate portfolio root)
  - all `.md` frontmatter in the portfolio tree
writes_to:
  - {file}.rendered.md (with --write-companion)
  - {file} (with --rewrite-inline, destructive)
consumed_by:
  - Obsidian + Dataview for live rendering (they ignore this skill)
  - static-report pipelines (CI, docs-site builds, GitHub READMEs)
  - `document-define` templates — generated types with `priority` or
    `health` fields emit queries that use the canonical glyph mappings
</dependencies>
