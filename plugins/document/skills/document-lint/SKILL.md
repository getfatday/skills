---
name: document-lint
description: >
  Detect and fix document health issues in a typed document portfolio:
  type drift (content doesn't match declared type), unlinked people references
  (plain-text names instead of markdown links to People files), orphaned
  documents (files not cataloged in any index), broken wikilinks in
  relationship fields, and stale `inferred: true` markers that need human
  verification. Use this skill whenever the user mentions document health,
  portfolio audit, lint, drift, broken links, orphaned docs, mistyped
  documents, inferred markers, or asks to clean up the portfolio. Also use
  when the user says things like "something seems off with these docs",
  "check for problems", "are there any issues", or "tidy up the portfolio".
materialized: "2026-04-18"
user-invocable: true
trigger-phrases:
  - "lint the documents"
  - "check document health"
  - "audit the portfolio"
  - "find mistyped documents"
  - "fix broken links"
  - "find orphaned docs"
  - "find broken wikilinks"
  - "find stale inferred"
  - "clean up the portfolio"
  - "document-lint"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
---

# document-lint

Detect and fix five categories of document health issues in a typed portfolio.

## When to Run

Run this skill when:
- The user asks to check, audit, or clean up documents
- You notice documents that look like they might be the wrong type
- You're onboarding to a portfolio and want to understand its health
- After bulk imports or migrations that may have introduced drift

## Setup

Before doing anything, locate the portfolio's document system:

1. Find the root document: `.config/documents/root.md`
2. Load type definitions: `.config/documents/types/*.md`
3. Find the People directory (declared in the root type's Collections table)
4. Build a map of `type name -> required fields + required sections` from the type definitions

If any of these are missing, tell the user — this skill requires a typed document system (the kind `document-define` creates).

## Checks

Run all five checks, then present a unified report. Fix issues as you go rather than just reporting them — but confirm with the user before retyping a document (checks 1c and 1d), since that's a judgment call. Checks 4 and 5 are reported-only by default; ask before editing.

### Check 1: Type Drift

A document has "type drift" when its frontmatter says one type but its content structure matches a different type better. This happens naturally as documents evolve — someone starts writing a research doc, and it turns into a decision record. Or a Jira sync creates milestone maps that get filed as research because there was no better type at the time.

**How to detect it:**

For each typed markdown file in the portfolio tree:

a. **Missing required sections.** Read the type definition for the document's declared type. Check whether each required section heading exists in the document body. A document typed as `research` without a `## Findings` section is drifted.

b. **Missing required fields.** Check whether each required frontmatter field (beyond `type` itself) is present. A milestone without `status` is incomplete.

c. **Content matches a different type better.** This is the harder case. When a document is missing required sections for its declared type, scan the other type definitions and see if the document's actual sections and fields are a closer match to a different type. A document with `## Overview`, `## Success Criteria`, and a `jira_ticket` field is probably a milestone, regardless of what its `type:` field says.

d. **Repeated structural patterns suggest a missing type.** If multiple documents share the same undeclared structure (e.g., 14 "Milestone Map" files that are all tables with the same columns), that pattern probably deserves its own type definition. Flag the cluster and suggest the user run `/document:document-define` to formalize it.

**How to fix:**

- For (a) and (b): If the document genuinely is the declared type but just missing content, add stub sections with a TODO comment. If the document clearly isn't that type, proceed to (c).
- For (c): Propose a retype. Show the user: "This file is typed as {current} but its structure matches {suggested} — it has {evidence}. Retype it?" On confirmation, update the `type:` field and restructure the frontmatter to match the new type's required fields.
- For (d): Group the similar documents, show the pattern, and suggest creating a new type via `/document:document-define`.

### Check 2: Unlinked People References

The portfolio convention is that people references in frontmatter use markdown link syntax pointing to a People file:

```yaml
author: "[Lucy Meadow](../../People/lmeadow.md)"
```

But in practice, people are often written as plain text: `author: Lucy Meadow` or `lead: Ed Hodges`. This breaks the link graph and makes it impossible to trace who owns what.

**How to detect it:**

Scan frontmatter fields that reference people. The common fields are:
- `author`, `lead`, `owner`, `assignee`, `deciders`, `engineering_leader`, `manager`, `reports-to`

For each value, check whether it's a markdown link (contains `[` and `](`). If it's plain text:
1. Search the People directory for a matching file (try matching on the `name:` field in each person's frontmatter, or on `userid`)
2. If found, compute the correct relative path from the document to the People file
3. If not found, the person needs a People file created first

**How to fix:**

- **Person file exists:** Replace the plain-text name with a markdown link. For example, `author: Lucy Meadow` becomes `author: "[Lucy Meadow](../../People/lmeadow.md)"`. Compute the relative path correctly based on the document's location.

- **Person file doesn't exist:** Create a minimal person file in the People directory using whatever information you can gather from the portfolio (name, role from context, any email patterns). Use the person's likely userid as the filename (first initial + last name, lowercase). Update the People/index.md table. Then link the reference.

- **Comma-separated lists** (like `deciders: Lucy Meadow, Evano Pescatore`): Split, resolve each person, and reformat as a YAML list of links.

### Check 3: Orphaned Documents

An orphaned document exists in the portfolio tree but isn't referenced from any index.md or parent document. It's invisible to anyone navigating the portfolio.

**How to detect it:**

1. Collect all typed markdown files in the portfolio (excluding `.config/`, `.claude/`, `scripts/`, `docs/`)
2. Collect all markdown links from every `index.md` file
3. Any typed file not referenced by at least one index.md is orphaned

Also check for directories that should have an index.md but don't — this is often the cause (a directory was created, documents were added, but no index was created to catalog them).

**How to fix:**

- If the orphaned document belongs in an existing directory that has an index.md, add it to that index's table.
- If the orphaned document is in a directory without an index.md, create the index following the portfolio convention (title, description line, table of contents, count line).
- If the orphaned document doesn't belong where it is (e.g., it's in a root-level directory that shouldn't exist), suggest moving it to the correct location based on its type and content.

### Check 4: Wikilink Integrity

Every frontmatter field typed `link` or `links` in a type definition
must resolve to an existing file. Broken references break the document
graph and make lifecycle actions (e.g., "notify the parent project")
silently no-op.

**How to detect it:**

1. For each typed markdown file, read its frontmatter.
2. For each type-definition field declared as `link` or `links`, read
   the field's value.
3. For each wikilink in the value (string `[[Target]]` or piped
   `[[Path|Display]]`), resolve the target:
   - If the value is `[[Path/To/File|Name]]`, check whether
     `Path/To/File.md` exists under the portfolio root (strip trailing
     `/index` if present, then append `.md`).
   - If the value is `[[Name]]`, search the portfolio for any file
     whose `name:` frontmatter field or basename matches. No match =
     broken.
4. Also flag values that look like plain text (missing brackets) on
   link-typed fields. This is a subtype of the people-link check but
   applies to ANY `link` or `links` field.

**How to fix:**

- **Broken target:** surface the broken value and offer to
  (a) run `/document:enrich <type> --field <name>` to propose a
  matching target via fuzzy-match, (b) let the user paste the correct
  link, or (c) leave the field empty and mark `inferred: true` so
  `document-verify-inferred` picks it up later.
- **Plain-text value on a link field:** same flow as Check 2 (People),
  but parameterized by the type-definition's declared link fields
  rather than a hardcoded list. Look up the referenced entity in the
  target type's collection, compute the relative path, and rewrite.

This rule works across any document type — it reads link-typed fields
from the type definitions at runtime. Nothing is hardcoded.

**Caveat on aliases.** If the vault uses Obsidian aliases (where a
file's `aliases:` frontmatter lets it be referenced under alternate
names), the lint resolver won't know the alias unless it reads every
target file's `aliases:`. Treat "broken target" hits as candidates,
not findings — surface them for user confirmation before rewriting.
When in doubt, offer to run `/document:enrich <type> --field <name>`
to re-match via fuzzy instead of assuming the link is truly broken.

### Check 5: Stale Inferred Markers

Documents carrying `inferred: true` were populated by automation (e.g.,
`document-enrich`) and still need human verification. When the marker
lingers, the document's fields may drift from reality. Flag any
`inferred: true` older than 30 days as "needs verification".

**How to detect it:**

1. Glob typed markdown files.
2. For each file, check whether the frontmatter contains a line
   matching `^inferred:\s*true\s*$`.
3. Compute the file's age using `created:` (frontmatter) if present,
   falling back to mtime. A marker is "stale" if the age exceeds 30
   days.
4. Group stale documents by type so the user can decide to walk one
   type at a time.

**How to fix:**

- Do NOT auto-strip stale markers. The marker's purpose is to force a
  human look.
- Recommend `/document:verify-inferred` to the user (or
  `/document:verify-inferred --type <name>` to scope to a single
  type). That skill walks documents one-by-one and prompts Confirm /
  Correct / Skip.
- In batch mode, this rule can produce the prioritized queue that
  `document-verify-inferred --batch` consumes.

This rule is type-agnostic: it looks for the `inferred: true` marker
regardless of document type.

## Output

After running all checks and applying fixes, produce a summary:

```
## Document Lint Results

### Fixed
- {count} unlinked people references resolved ({new} new People files created)
- {count} orphaned documents cataloged in indexes
- {count} documents with missing required sections got TODO stubs
- {count} broken wikilinks repaired (field + target noted)

### Needs Review
- {count} documents may be mistyped (see below)
- {count} document clusters suggest a new type definition
- {count} wikilinks still broken (run /document:enrich to propose fixes)
- {count} documents carry `inferred: true` older than 30 days

### Type Drift Candidates
| File | Current Type | Suggested Type | Evidence |
|------|-------------|----------------|----------|
| ... | ... | ... | ... |

### New Type Candidates
| Pattern | Count | Example Files |
|---------|-------|---------------|
| ... | ... | ... |

### Broken Wikilinks
| File | Field | Broken Target | Suggested Action |
|------|-------|---------------|------------------|
| ... | ... | ... | ... |

### Stale Inferred Markers
| File | Type | Age (days) | Suggested Action |
|------|------|------------|------------------|
| ... | ... | ... | /document:verify-inferred |
```

## Scope Control

By default, lint the entire portfolio. But if the user specifies a path ("lint Strategies/"), scope to that subtree. If the user specifies a check ("just check for orphans"), run only that check. Supported single-check flags: `--drift`, `--people`, `--orphans`, `--wikilinks`, `--inferred`.

## Type-Agnostic Contract

All five checks read type definitions at runtime from
`.config/documents/types/*.md`. Nothing hardcodes a type name or field
name. Checks 4 (wikilink integrity) and 5 (stale inferred) were added
as part of the plugin's portable document-graph hygiene; they operate
across every document type the portfolio defines and every link-typed
field those types declare.
