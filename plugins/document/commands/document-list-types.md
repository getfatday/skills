---
name: document:list-types
description: List all defined document types and their generation status
allowed-tools:
  - Read
  - Glob
  - Grep
---

<objective>
Show all defined document types, their descriptions, locations, and whether their generated skills are up to date.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-define/SKILL.md` → `list-types` operation.
</workflow>
