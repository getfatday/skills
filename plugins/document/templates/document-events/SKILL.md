---
name: document-events
tier: 2-materialized
description: >
  Query the change-event log of a typed document portfolio. Derives events
  from git history — every create, update, status change, rename, and delete
  of a typed document is an event — and answers questions about what changed,
  when, and by whom. Use this skill when the user asks about document history,
  the event log, a changelog, an audit trail, what changed recently, who last
  touched a document, recent status transitions, or activity across the
  portfolio. Also use for phrasings like "what happened to this doc", "show me
  recent changes", "who edited X", "what moved to review this week", or "catch
  me up on the docs".
materialized: "2026-05-22"
user-invocable: true
trigger-phrases:
  - "document events"
  - "document event log"
  - "document history"
  - "what changed in the documents"
  - "what changed recently"
  - "who edited this document"
  - "recent status transitions"
  - "catch me up on the docs"
  - "document changelog"
  - "document audit trail"
allowed-tools: [Read, Bash, Glob, Grep]
---

# document-events

Query the change-event log of a typed document portfolio. The log is *derived*
from git history — it is never stored. See
`skills/document-define/references/event-model.md` for the full event model.

This skill is **read-only**. It never writes to the portfolio: the event log is
a view over commits that already happened.

## When to Run

Run this skill when the user wants to know:

- What changed in the portfolio, and when
- The history of one document — every event in its life
- Who last touched a document, or who has been active
- Which documents transitioned status (e.g. what moved to `review`)
- A catch-up digest of recent activity

## Setup

1. Find the portfolio: locate `.config/documents/root.md` by searching the
   current directory and its parents. If there is no typed document system,
   tell the user — this skill needs the kind of portfolio `document-define`
   creates.
2. Confirm the portfolio is inside a git repository (`git rev-parse
   --show-toplevel`). The event log is derived from commits; with no git
   history there are no events.
3. The deriver script ships with this plugin at
   `$(git rev-parse --show-toplevel)/.claude/skills/document-events/scripts/derive-events.py`. It is a zero-dependency
   Python 3 script — no install step. Invoke it with `python3` and point `-C`
   at the repository:

   ```bash
   python3 "$(git rev-parse --show-toplevel)/.claude/skills/document-events/scripts/derive-events.py" -C <repo-root> <subcommand> [options]
   ```

   It emits a JSON array of events. Each event carries `id`, `ts`, `commit`,
   `actor`, `document`, `type`, `op`, `changes`, and `message`.

## Operations

Route the user's request to one of three operations. Each shells out to the
deriver, parses the JSON, and presents a readable summary — not raw JSON,
unless the user asks for it.

### log — query the event stream

The general query. Run `derive-events.py log` with the filters the user
implied:

- `--type <type>` — only events for one document type (e.g. `prd`)
- `--op <op>` — only one operation: `created`, `updated`, `deleted`,
  `renamed`, `status-changed`
- `--document <substring>` — only documents whose path contains the substring
- `--since <ISO-date>` — only events at or after a date (e.g. `2026-05-01`)

Combine filters freely. Example — "what PRDs moved status this month":

```bash
python3 "$(git rev-parse --show-toplevel)/.claude/skills/document-events/scripts/derive-events.py" -C <repo> \
  log --type prd --op status-changed --since 2026-05-01
```

Present the result as a table: date, document, op, what changed, actor.

### history — the life of one document

When the user names a document, run `log --document <path-or-name>` and present
every event in chronological order — a timeline. Highlight status transitions
and creation. If the substring matches multiple documents, list them and ask
which one.

### digest — catch-up summary

When the user wants to be caught up ("what's been happening", "anything new"),
run `derive-events.py log --since <recent-date>` (default to the last 14 days
unless the user gives a range). Summarize rather than list every event:

- Counts by operation (`N created, N updated, N status-changed, ...`)
- Counts by type
- Notable status transitions, called out individually
- The most active documents and actors

## Output

Lead with a direct answer to what the user asked. Then show supporting detail
as a markdown table. Keep raw JSON out of the response unless the user asks for
it (offer "want the raw events?" when the result is large).

If the deriver reports `error:` on stderr (not a git repo, bad rev range),
surface that plainly and suggest the fix.

If the log is empty, say so explicitly and why — no commits yet, no typed
documents, or the filters excluded everything.
