---
name: document:verify-inferred
description: "Walk documents carrying an inferred marker and prompt to Confirm, Correct, or Skip each"
argument-hint: "[--type <name>] [--path <glob>] [--batch]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Review all documents that carry `inferred: true` in their frontmatter,
one at a time, and confirm / correct / skip each.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-verify-inferred/SKILL.md`:

- No arguments → walk the full portfolio
- `--type <name>` → restrict to one document type
- `--path <glob>` → restrict to a subtree
- `--batch` → print summary only, no prompting

The skill handles type discovery, prompting, and frontmatter editing.
</workflow>
