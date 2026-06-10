# Event Model

The document event log treats git history as a write-ahead log. Every change
to a typed document is an **event**, and the event log is a *derived view* over
the commit history — never a stored artifact.

This reference defines what an event is, how events are derived, and the
guarantees the deriver must hold. The deriver itself is
`plugins/document/scripts/derive-events.py`.

## Git history as a write-ahead log

A relational database records every change in a write-ahead log (WAL) and
*derives* downstream views — replicas, change streams, audit tables — from it.
The document plugin already has a WAL: the git history of the document
portfolio.

A **typed document** is any Markdown file that carries a `type:` frontmatter
field. Document instances are scattered across the portfolio at paths their
hosting types declare — they do *not* live under `.config/documents/`, which
holds only configuration (`root.md`, `types/`). The deriver therefore detects
documents by their frontmatter, not by location.

- A **commit** is a transaction. It lands atomically — all files in it, or none.
- The **history** is the WAL — an ordered, immutable, content-addressed record
  of every transaction.
- An **event** is one document's change within one commit, recovered by diffing
  that commit against its parent.

Because the WAL already exists, events are never written or stored. They are
*derived* on demand. `events = f(commit-DAG)` — a pure function of history.
Re-running the deriver on the same commits yields the same events, on any
clone, forever.

## The event schema

Each event is a JSON object:

```json
{
  "id":       "a1b2c3d4:Products/Checkout/prd.md:0",
  "ts":       "2026-05-22T14:03:11Z",
  "commit":   "a1b2c3d4e5f6...",
  "actor":    "Ian Anderson <ian@example.com>",
  "document": "Products/Checkout/prd.md",
  "type":     "prd",
  "op":       "status-changed",
  "changes": [
    { "field": "status", "from": "draft", "to": "review" }
  ],
  "message":  "prd: move Checkout to review"
}
```

| Field | Meaning |
|-------|---------|
| `id` | `{commit}:{document}:{seq}` — content-addressed, stable, globally unique |
| `ts` | commit author date, ISO-8601 UTC |
| `commit` | full commit SHA the event was derived from |
| `actor` | commit author (`Name <email>`) |
| `document` | repo-relative path of the document file |
| `type` | the document's `type:` frontmatter value, or `null` if untyped |
| `op` | the operation class (see taxonomy below) |
| `changes` | structured deltas — field changes and section changes |
| `message` | commit subject line |

### The `changes` array

Two shapes appear in `changes`:

- **Field delta** — a frontmatter field changed:
  `{ "field": "owner", "from": "alice", "to": "bob" }`. A newly added field has
  `"from": null`; a removed field has `"to": null`.
- **Section delta** — an H2 section was added, removed, or modified:
  `{ "section": "Problem Statement", "change": "modified" }` where `change` is
  one of `added`, `removed`, `modified`.

`changes` is empty only for `created` and `deleted` events, where the operation
itself is the whole story.

## The `op` taxonomy

`op` classifies the document-level change. Exactly one applies per event.

| `op` | When |
|------|------|
| `created` | the document file did not exist in the parent commit |
| `deleted` | the document file existed in the parent but not in this commit |
| `renamed` | git detected the file moved (the `document` field is the new path; a `from-path` field carries the old path) |
| `status-changed` | the frontmatter status field changed value (a field delta on the type's lifecycle status field) |
| `updated` | any other change — field deltas and/or section deltas |

`status-changed` takes precedence over `updated`: if a commit changes the
status field *and* other fields, the event is `status-changed` and `changes`
carries every delta. This makes lifecycle transitions trivially queryable
without inspecting `changes`.

## The derivation algorithm

The deriver produces the event log deterministically:

1. **Walk history.** `git log --first-parent --reverse -- '*.md'`.
   `--first-parent` pins a single canonical traversal so the log is identical
   regardless of how branches were merged. `--reverse` yields oldest-first.
2. **For each commit, diff against its first parent.** `git diff-tree` the
   commit against its first parent with rename detection, restricted to
   Markdown files. The initial commit is diffed against the empty tree.
3. **For each changed Markdown file** that is a typed document — has a `type:`
   frontmatter field before or after the change, and is not under `.config/` or
   `.claude/` — in path-sorted order:
   - Read the file content before and after (from the two tree objects).
   - Parse frontmatter before and after; diff the fields.
   - Parse H2 section headings and bodies before and after; diff the sections.
   - Classify `op` from the file's add/delete/rename status and the field
     deltas.
   - Emit one event.
4. **Assign `seq`** — see below.
5. **Compute `id`** as `{commit}:{document}:{seq}`.

Markdown files that are not typed documents, and any files under `.config/` or
`.claude/`, are ignored.

### `seq` ordering

A single commit can touch many documents. `seq` disambiguates events sharing a
commit:

- Within a commit, changed documents are sorted by repo-relative path
  (byte order, ascending).
- `seq` is the zero-based index of the document in that sorted list.

Because the sort key is the path and the path set is fixed by the commit, `seq`
is a pure function of the commit — never of wall-clock time, filesystem order,
or traversal order. Two derivations of the same commit assign identical `seq`
values.

## The determinism contract

The deriver MUST satisfy these properties. They are what make the event log
trustworthy as a derived view, and they are the load-bearing tests in
`test_derive_events.py`.

1. **Reproducible.** Deriving the same commit range twice yields byte-identical
   JSON.
2. **Clone-independent.** Two independent clones of the same history derive
   byte-identical events. No machine-local state (timestamps, usernames,
   filesystem ordering, absolute paths) leaks into an event.
3. **Content-addressed ids.** `id` is a function of commit SHA, document path,
   and `seq` — all of which are fixed by history. The same logical change has
   the same `id` everywhere, with no coordination.
4. **Append-only under fast-forward.** Adding commits to history only appends
   events; it never changes events already derived from earlier commits.

Determinism is why the log needs no storage and no central authority: any
consumer re-derives it and gets the same answer.

## What is not an event

- **Uncommitted working-tree edits.** A change is an event only once committed.
  Before that it is an in-flight transaction.
- **Changes to files that are not typed documents** (no `type:` frontmatter),
  and any files under `.config/` or `.claude/`.
- **Merge commits themselves.** `--first-parent` traversal means a merge's
  second-parent commits are not visited as separate transactions; their net
  effect appears in the first-parent diff of the merge commit.

## Future work — reacting to events

This reference specifies the event *log* only: deriving and querying events.
*Reacting* to events — triggers, subscriptions, handlers, and any per-type
declaration of what should happen when an event occurs — is intentionally out
of scope and not specified here.

The schema is forward-compatible with that future: events are stable, identified
values, so a trigger layer can be added later as a pure consumer of this log
without changing how events are derived.
