---
name: document:render
description: Render a document's dataview code blocks into static markdown tables
argument-hint: "<file> [--write-companion|--rewrite-inline] [--portfolio <path>]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

<objective>
Materialize the dataview code blocks in a document into static markdown
tables. Runs without Obsidian.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-render/SKILL.md`:

- `/document:render <file>` → render to stdout (preview mode)
- `/document:render <file> --write-companion` → writes `{file}.rendered.md`
- `/document:render <file> --rewrite-inline` → overwrites `<file>` in place
- `--portfolio <path>` → override the auto-detected portfolio root

The skill runs `scripts/render.py`, which parses the supported DQL
subset and emits GitHub-flavored markdown tables.
</workflow>
