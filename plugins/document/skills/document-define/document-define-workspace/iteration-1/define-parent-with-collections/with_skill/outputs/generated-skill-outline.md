# Generated Skill Outline: program

## Skill Metadata

- name: program
- generated-by: document-define
- generator-version: "1.1"
- type-definition: ".config/documents/types/program.md"
- user-invocable: false
- allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion]

## Objective

Manages Program documents. Handles creation, retrieval, listing, validation, and lifecycle transitions. Programs host child collections of initiatives and epics.

## Vault Schema

- File ownership: `./Programs/{name}/index.md` (resolved from root type Collections table)
- Required frontmatter: type, name, status, created
- Optional frontmatter: quarter
- Required sections: Overview
- Optional sections: Roadmap

## Operations

### create

1. Prompt user for required fields: name, status, created (default today).
2. Prompt for optional field: quarter.
3. Prompt user for Overview section content.
4. Resolve path: `./Programs/{name}/index.md` (from root Collections table).
5. Write the document with frontmatter and sections.
6. **Scaffold collection directories:**
   - Create `./Programs/{name}/initiatives/` directory if it does not exist.
   - Create `./Programs/{name}/initiatives/index.md` with empty `## Contents` section.
   - Create `./Programs/{name}/epics/` directory if it does not exist.
   - Create `./Programs/{name}/epics/index.md` with empty `## Contents` section.
7. Update `./Programs/index.md` collection index with a link to the new program.
8. Confirmation message listing: file created, fields set, collections scaffolded (initiatives, epics).

### get

1. Read program document by name or path.
2. Display frontmatter summary and section headings.
3. **Enumerate collections:**
   - Glob `./Programs/{name}/initiatives/*.md` (excluding index.md). Show count and links.
   - Glob `./Programs/{name}/epics/*.md` (excluding index.md). Show count and links.
4. Always produce output even if not found.

### list

1. Read `./Programs/index.md` or glob `./Programs/*/index.md`.
2. Display as table: name, status, created, quarter.
3. **Include collection counts column:** e.g., "3 initiatives, 5 epics".
4. If no programs exist, say so explicitly.

### validate

1. Check required frontmatter fields: type, name, status, created.
2. Check `type` equals "program".
3. Check `status` is one of: active, paused, completed.
4. Check required sections: Overview exists.
5. Check collection directories exist and have index files.
6. Report pass/fail per field and section.

### update-status

1. Validate transition against allowed transitions:
   - active -> paused
   - paused -> active
   - active -> completed
   - paused -> completed
2. If invalid, reject with error message listing allowed transitions from current status.
3. If valid, update the status field and report the transition.

## Template

The generated template at `.claude/skills/program/templates/program.md`:

```yaml
---
type: program
name: {name}
status: active
created: {YYYY-MM-DD}
quarter:
---
```

```markdown
## Overview

{Program overview}

## Roadmap

```

## Command

The generated command at `.claude/commands/program.md` routes:
- `/program create` -> create operation
- `/program list` -> list operation
- `/program get {name}` -> get operation
- `/program validate` -> validate operation
- `/program status {name} {new-status}` -> update-status operation

No split/merge routes (program type has no Facets table).

## Key Behaviors for Collections

1. **On create:** scaffold `initiatives/` and `epics/` subdirectories with index.md files inside each program directory.
2. **On get:** glob child collections and display summary counts with links.
3. **On list:** show aggregate collection counts per program in a table column.
4. **On validate:** verify collection directories and indexes exist under the program directory.
