---
name: document:define
description: Define a new document type or regenerate from an existing type definition
argument-hint: [type-name]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Define a new document type conversationally, or regenerate a skill from an existing type definition.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-define/SKILL.md`:

- No arguments or new type name → `define` operation (conversational)
- Existing type name → `generate` operation (regenerate from definition)
- `--regenerate <type>` → `regenerate` operation

The skill handles all interaction, type definition writing, and skill generation.
</workflow>
