---
name: document-verify-inferred
description: >
  This skill should be used whenever the user wants to review,
  confirm, or correct documents whose frontmatter carries an
  `inferred` marker — the reserved flag that scanners like
  document-enrich set when they populate fields by inference rather
  than direct input. Trigger liberally: invoke it any time the user
  mentions walking through inferred documents, cleaning up pending
  verifications, sanity-checking auto-guessed values, processing
  stale inferred markers flagged by document-lint, accepting or
  overriding automation-populated fields on a document-by-document
  basis, or running a yes/no/fix review loop over documents left by a
  backfill script. Typical phrasings include "review inferred
  markers", "walk through docs with inferred true", "verify the
  auto-guessed project fields", "clean up the inferred flags from
  last month's backfill", "which documents still need human
  verification?", "help me sign off on enrichment results one by
  one", or invoking /document:verify-inferred directly. Also fires
  after document-enrich runs when the user wants to audit the
  resulting markers, or after document-lint flags stale inferred
  markers older than 30 days. Walks any typed document with the
  marker — no type or field name is hardcoded. Even if the user
  doesn't say "inferred", trigger this skill when the task is clearly
  about reviewing automation-generated annotations for correctness.
materialized: "2026-04-18"
user-invocable: true
trigger-phrases:
  - "verify inferred"
  - "review inferred documents"
  - "clean up inferred markers"
  - "document-verify-inferred"
  - "which documents need verification"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
---

# document-verify-inferred

<objective>
The `inferred: true` marker is a reserved convention on typed documents
(see `references/type-definition-schema.md`). A scanner — typically
`document-enrich`, a creation hook, or some other automation — sets it
when it populates a field by inference rather than direct user input.
This skill walks the portfolio, surfaces every document still carrying
the marker, and prompts the user to either Confirm (delete the marker),
Correct a field and then delete the marker, or Skip and come back later.

Zero type-specific logic: the skill discovers document types at runtime
from `.config/documents/types/*.md` and operates on any document that
carries the marker.
</objective>

## When to Run

- After `/document:enrich` has written proposals and the user wants to
  audit what the enrichment inferred
- On a cadence (weekly) to keep the inferred queue short
- When `/document:lint` reports stale inferred markers (older than
  30 days) — this skill resolves them

## Setup

1. **Locate the portfolio.** Resolve `.config/documents/root.md`. If the
   file is missing, tell the user this skill needs a typed document
   system (the kind `document-define` creates) and exit.
2. **Discover types.** Glob `.config/documents/types/*.md`. For each,
   parse the `## Identity` section to read the `name:` slug.
3. **Discover instance paths.** For each type, resolve its path pattern
   by reading the root type's `## Collections` table (and any parent
   type's Collections/Facets tables). This is the same resolver
   `document-define` uses.

## Walk

**Inputs (optional):**
- `--type <name>` — restrict walk to instances of a single type
- `--path <glob>` — restrict walk to a subtree (e.g., `Sessions/`)
- `--batch` — print a summary of remaining inferred documents without
  prompting (non-interactive mode, useful for lint/CI)

**Steps:**

1. **Collect candidates.** Glob typed markdown files in the portfolio
   tree (skip `.config/`, `.claude/`, `scripts/`, `docs/`). Read each
   file's frontmatter. Keep files where a line matches `^inferred:\s*true$`.

2. **Sort oldest-first.** Use each file's `created:` date (or mtime as
   fallback) so the user sees the stalest inferred documents first. This
   matches the prioritized queue `document-lint` emits.

3. **For each candidate**, read the document's frontmatter. Identify
   which fields are *likely inferred* (the marker itself doesn't record
   WHICH fields were inferred — that's intentional; scanners sometimes
   infer multiple). A heuristic:
   - Any `link` or `links` field whose value is non-empty
   - Plus any field flagged in the document's `## History` section if one
     exists
   - Otherwise: show all link-typed fields from the type definition

4. **Prompt the user** via AskUserQuestion. Present:
   - The file path (relative to portfolio root)
   - The document's type and title
   - The candidate-inferred fields and their current values

   Options (three, single-select):
   - **Confirm** — value is right; strip the `inferred: true` line
   - **Correct** — value is wrong; prompt for a replacement, write it,
     then strip the marker
   - **Skip** — leave as-is, move to next candidate

5. **Apply the choice.**
   - *Confirm*: delete the `inferred: true` line from frontmatter. Write
     the file back. Keep all other content unchanged.
   - *Correct*: prompt the user (second AskUserQuestion) for which field
     to edit; then read the new value as free text. Write the new value
     into the field, delete the `inferred: true` line, save.
   - *Skip*: no write. Continue.

6. **Between prompts, offer an early exit.** After every 5 candidates
   (or at the user's request), ask whether to continue or stop for now.
   The walk is resumable — running the skill again picks up where the
   user left off, since confirmed/corrected files no longer carry the
   marker.

## Correction Flow — Details

When the user chooses *Correct*, ask which field to edit (dynamic list
built from the document's frontmatter fields that are declared `link`,
`links`, or `string` in the type definition). For link-typed fields:

- If the type definition declares `links-to: {target-type}` on this
  field, glob the portfolio for instances of that target type and offer
  them as options (up to the AskUserQuestion 4-option limit; otherwise
  accept free text).
- Write the new value preserving the existing quoting style (wiki-link
  `"[[Target]]"` vs plain link).

For enum-typed fields: read the allowed values from the type definition
and present as options.

For plain string fields: accept free text.

## Batch Mode

When invoked with `--batch`, skip prompting entirely. Instead produce a
summary table:

```
## Inferred-Marker Queue

{N} documents still carry `inferred: true`. Oldest first:

| File | Type | Age (days) | Candidate fields |
|------|------|------------|------------------|
| ... | ... | ... | ... |
```

Useful for `document-lint`'s stale-inferred check to cite specific
files.

## Output

After the walk, print a summary:

```
## Verified

- Confirmed: {count}
- Corrected: {count}
- Skipped: {count}
- Remaining with `inferred: true`: {count}
```

## Design Principles

1. **Zero type-specific logic.** The skill reads type definitions at
   runtime. It works against `session`, `epic`, `decision`, or any
   type with a link-typed field.
2. **Never write without user confirmation.** Every edit goes through
   an AskUserQuestion response.
3. **Idempotent.** Running the skill twice does nothing on confirmed
   documents.
4. **Resumable.** The skill has no state; it just walks what's still
   inferred.
5. **The marker is a fact, not a flag.** `inferred: true` records that
   at least one field was populated by inference. Confirming doesn't
   mean the value was wrong — it means a human endorsed it.

<dependencies>
reads_from:
  - .config/documents/root.md (in consuming project)
  - .config/documents/types/*.md (type definitions, in consuming project)
  - all typed markdown documents in the portfolio tree
writes_to:
  - individual document files (removes `inferred: true` on confirm/correct)
consumed_by:
  - document-lint (stale-inferred rule family surfaces the queue this skill drains)
  - human reviewers after `/document:enrich` runs
</dependencies>
