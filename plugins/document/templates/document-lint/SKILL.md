---
name: document-lint
tier: 2-materialized
description: >
  Detect and fix document health issues in a typed document portfolio:
  type drift (content doesn't match declared type), unlinked people references
  (plain-text names instead of markdown links to People files), orphaned
  documents (files not cataloged in any index), broken wikilinks in
  relationship fields, stale `inferred: true` markers that need human
  verification, declared-supersession integrity (missing back-links, cycles,
  orphans), and (opt-in) inferred semantic contradictions between related
  docs. Use this skill whenever the user mentions document health,
  portfolio audit, lint, drift, broken links, orphaned docs, mistyped
  documents, inferred markers, supersession, contradictions, or asks to clean
  up the portfolio. Also use when the user says things like "something seems
  off with these docs", "check for problems", "are there any issues", or
  "tidy up the portfolio".
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
  - "check supersession"
  - "find supersession violations"
  - "find contradictions"
  - "semantic drift"
  - "document-lint"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
---

# document-lint

Detect and fix seven categories of document health issues in a typed
portfolio. Five are structural (Checks 1–5, default-on). Two are
semantic: declared-supersession integrity (Check 6a, default-on) and
inferred contradiction sweep (Check 6b, opt-in via `--semantic`).

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

Run all six default checks (1–5 and 6a) by default, then present a
unified report. Check 6b is opt-in (see `--semantic` under Scope
Control). Fix issues as you go rather than just reporting them — but
confirm with the user before retyping a document (checks 1c and 1d),
since that's a judgment call. Checks 4 and 5 are reported-only by
default; ask before editing. Check 6a auto-fixes only when the user
passes `--fix`.

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

### Check 6a: Declared Supersession Integrity

When one document replaces another, the convention is two reciprocal
fields: the new doc carries `supersedes: [[Old]]`, and the prior doc
carries `superseded-by: [[New]]`. A third field,
`supersedes-propagated: true`, is the idempotency marker the lint
writes once it has propagated the back-link, so re-runs are no-ops.

This check enforces the contract.

**How to detect it:**

Run `$(git rev-parse --show-toplevel)/.claude/skills/document-lint/scripts/supersession.py scan --portfolio <root> [--type <name>]`.
The script walks the portfolio for any doc whose frontmatter contains
`supersedes:` or `superseded-by:` and reports four classes of
violation:

a. **missing-back-link** — `A.supersedes = [[B]]` but B has no
   `superseded-by: [[A]]`.
b. **missing-forward** — `B.superseded-by = [[A]]` but A has no
   `supersedes: [[B]]`.
c. **orphan-back-link** / **orphan-forward** — the link target
   doesn't exist on disk (the prior or successor was deleted).
d. **cycle** — `A → B → A` (or any longer chain returning to a
   visited node). Cycles are reported, never auto-repaired.

**How to fix:**

Without `--fix`: violations land in the unified lint report; nothing
is written.

With `--fix` (i.e. `/document:lint --supersession --fix`): run
`$(git rev-parse --show-toplevel)/.claude/skills/document-lint/scripts/supersession.py fix --portfolio <root> [--type <name>]`. For
every missing-back-link or missing-forward pair, the script writes
the reciprocal field on the prior doc, sets
`supersedes-propagated: true` on the superseder, and (only when the
prior doc's type definition declares `superseded` as a valid status
in its `## Lifecycle` `- values:` line) sets `status: superseded` on
the prior doc. Cycles and orphans are NOT touched — the script's
`refused` counter records them so the unified report can surface them.

The `supersedes-propagated: true` marker is what makes re-running
`--fix` a no-op. Check 6a never strips or rewrites
`supersedes` on the superseder; it only propagates the back-link.

**Type-agnostic.** The check treats `supersedes` and `superseded-by`
as reserved fields supported across every type (declared in
`document-define/references/type-definition-schema.md`). The
`status: superseded` write is gated on the prior doc's type
definition, so types without a `superseded` lifecycle value see only
the back-link written and keep their existing status.

### Check 6b: Inferred Contradiction Sweep

Two related documents can carry incompatible facts even when neither
fails the structural checks. This sweep clusters likely-related docs
by shared signals, sends each cluster to the LLM with a
contradiction-finding prompt, and writes `contradiction-with: [[Other]]`
+ `inferred: true` to both sides of any flagged pair. Resolution is
left to the human via `/document:verify-inferred`.

**This check is opt-in.** It runs only when the user passes
`--semantic`, and `--semantic --dry-run` reports the cluster count
and estimated token cost without making any LLM calls.

**How to detect it:**

1. Run `$(git rev-parse --show-toplevel)/.claude/skills/document-lint/scripts/contradiction-cluster.py --portfolio <root>` (add
   `--type <name>` to scope to one type, `--min-shared N` to tighten
   the link-overlap signal). The script does NOT call any LLM. It
   walks the portfolio, builds two pair-wise relations:
   - **shared-links:** every pair of docs whose link-typed
     frontmatter fields point at ≥ N (default 3) common targets.
   - **shared-topics:** every pair of docs whose `tags` / `topics` /
     `categories` frontmatter overlap by ≥ 1 entry.

   Pairs are merged into clusters by transitive closure. The script
   emits JSON: `{"stats": {…}, "clusters": [{"id", "docs", "types",
   "shared_links", "shared_topics", "score", "estimated_tokens",
   "truncated"}]}`. Cluster cap defaults to 50 (`--max-clusters`);
   per-cluster member cap defaults to 12 (`--max-cluster-size`).
2. **Dry-run path:** if the user passed `--dry-run`, stop here.
   Print the cluster count and estimated total tokens from
   `stats`. Do not invoke the LLM. Do not write `contradiction-with`
   to any doc.
3. **Live path:** for each cluster, apply
   `references/contradiction-prompt.md`. That template specifies the
   prompt format, the per-call timeout (60 seconds), and the
   defensive checks for hallucinated paths. Skip clusters whose
   `estimated_tokens` exceeds 20,000.
4. For each pair the LLM returns: append `[[Other]]` to the
   `contradiction-with` list on both sides, set `inferred: true` on
   both sides. The `inferred: true` write is **mandatory** — without
   it, `/document:verify-inferred` won't surface the pair for human
   review.

**How to fix:**

This check never auto-resolves. The user owns resolution via
`/document:verify-inferred` (which the existing Check 5 already
points to). The lint report should call out the count of newly
flagged contradictions and the suggested next command.

**Cost discipline.** `--semantic --dry-run` is mandatory before any
live run. If the dry-run reports more than 20 clusters, recommend
narrowing scope (`--type`, `--min-shared 4`) before going live.

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

### Supersession Violations
| File | Kind | Detail | Suggested Action |
|------|------|--------|------------------|
| ... | missing-back-link | declares supersedes [[Old]] but Old lacks back-link | re-run with `--supersession --fix` |
| ... | cycle | A → B → A | manual: break the cycle |
| ... | orphan-back-link | superseded-by [[X]] but X is missing | manual: restore X or clear field |

### Inferred Contradictions (when --semantic)
| Cluster | Docs | Pairs Flagged | Estimated Tokens |
|---------|------|---------------|------------------|
| ...     | ...  | ...           | ...              |

After a `--semantic` live run, count the docs that gained a fresh
`contradiction-with` + `inferred: true` and remind the user to run
`/document:verify-inferred` to walk the new flags.
```

## Scope Control

By default, lint the entire portfolio with checks 1–5 and 6a. But if
the user specifies a path ("lint Strategies/"), scope to that
subtree. If the user specifies a check ("just check for orphans"),
run only that check.

Supported single-check flags:

- `--drift` — Check 1 only
- `--people` — Check 2 only
- `--orphans` — Check 3 only
- `--wikilinks` — Check 4 only
- `--inferred` — Check 5 only
- `--supersession` — Check 6a only (declared-supersession integrity).
  Combine with `--fix` to write the back-links.
- `--semantic` — Check 6b only (inferred contradiction sweep). Off by
  default; opt-in.
- `--semantic --dry-run` — cluster only; print cluster count and
  estimated total token cost; make zero LLM calls; write nothing.

`--type <name>` further restricts any of the above to a single
document type (passed through to `supersession.py` and
`contradiction-cluster.py`).

## Type-Agnostic Contract

All seven checks read type definitions at runtime from
`.config/documents/types/*.md`. Nothing hardcodes a type name or
field name. Checks 4 (wikilink integrity) and 5 (stale inferred) were
added as part of the plugin's portable document-graph hygiene; they
operate across every document type the portfolio defines and every
link-typed field those types declare. Checks 6a (declared
supersession) and 6b (inferred contradiction) reuse the same
contract — they read `supersedes`, `superseded-by`,
`supersedes-propagated`, and `contradiction-with` as reserved
optional fields available to every type.
