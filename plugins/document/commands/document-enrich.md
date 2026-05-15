---
name: document:enrich
description: Propose fuzzy-matched relationship-field values for instances of a document type
argument-hint: "<type> [--field <name>] [--apply <file>]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Enrich documents of a given type by inferring missing or legacy-format
relationship-field values via fuzzy match against candidate target-type
instances.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-enrich/SKILL.md`:

- `/document:enrich <type>` → `scan` operation (produces proposal YAML)
- `/document:enrich <type> --field <name>` → scan restricted to one relationship
- `/document:enrich --apply <file>` → `apply` operation (writes confirmed proposals)
- `/document:enrich <type> --orphans` → `list-orphans` operation (pure read)

The skill handles portfolio resolution, running the backbone script,
and summarizing results.
</workflow>
