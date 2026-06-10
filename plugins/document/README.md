# document

A meta-skill plugin for defining document types and generating per-type management skills.

## What it does

The `document` plugin provides a document type system for Claude Code projects. You define what a document type IS (fields, sections, relationships, lifecycle), and the plugin generates a complete management skill for that type.

**Type definitions** describe document types declaratively in markdown. They live in your project at `.config/documents/types/`.

**Generated skills** handle CRUD operations, lifecycle transitions, validation, and relationship management. They go into your project's `.claude/skills/` directory.

The plugin ships the meta-skill (`document-define`) and the schema reference. Your project owns all type definitions and the root document.

## Commands

| Command | Description |
|---------|-------------|
| `/document:define` | Define a new document type (conversational) or regenerate from an existing definition |
| `/document:list-types` | List all defined document types and their generation status |
| `/document:events` | Query the change-event log — what changed, when, and by whom |

## How it works

1. Run `/document:define` to describe a new document type conversationally
2. The skill asks about fields, sections, relationships, lifecycle, and creation mode
3. It writes a type definition to `.config/documents/types/{name}.md`
4. It generates a complete management skill at `.claude/skills/{name}/SKILL.md`
5. Use the generated `/{name}` command to create, list, get, validate, and transition documents

## Project structure

```
your-project/
  .config/documents/
    root.md                    # Project manifest (auto-created)
    types/
      brand.md                 # Type definition (you define these)
      prd.md                   # Type definition
  .claude/
    skills/
      brand/SKILL.md           # Generated skill
      prd/SKILL.md             # Generated skill
    commands/
      brand.md                 # Generated command
      prd.md                   # Generated command
```

## Event log

`/document:events` answers questions about how the portfolio changed over
time. It treats git history as a write-ahead log: every commit is a
transaction, and every create, update, status change, rename, or delete of a
typed document is an **event**.

The event log is *derived*, never stored — `scripts/derive-events.py` walks
`git log` and reconstructs events deterministically, so the same history
yields the same log on any clone. The script is a zero-dependency Python 3
script that runs in place; there is nothing to install.

```
/document:events                          # catch-up digest of recent activity
/document:events log --type prd --op status-changed --since 2026-05-01
/document:events history Products/Checkout/prd.md
```

The feature is read-only — it never writes to the portfolio. See
`skills/document-define/references/event-model.md` for the event schema and
the derivation algorithm.
