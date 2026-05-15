# document

A meta-skill plugin for defining document types and generating per-type management skills, plus tools for keeping a document portfolio healthy.

## What it does

The `document` plugin provides a document type system for Claude Code projects. You define what a document type IS (fields, sections, relationships, lifecycle, custom logic), and the plugin generates a complete management skill for that type. It also ships portfolio-level tools to enrich missing relationships, verify inferred markers, render Dataview queries outside Obsidian, and lint for drift.

**Type definitions** describe document types declaratively in markdown. They live in your project at `.config/documents/types/`.

**Generated skills** handle CRUD operations, lifecycle transitions, validation, and relationship management. They go into your project's `.claude/skills/` directory.

The plugin ships the meta-skill (`document-define`), portfolio skills (`document-enrich`, `document-lint`, `document-render`, `document-verify-inferred`), schema references, hooks, and helper scripts. Your project owns all type definitions and the root document.

## Commands

| Command | Description |
|---------|-------------|
| `/document:define` | Define a new document type (conversational) or regenerate from an existing definition |
| `/document:list-types` | List all defined document types and their generation status |
| `/document:enrich` | Propose fuzzy-matched values for missing relationship fields across instances of a type |
| `/document:verify-inferred` | Walk documents with inferred markers and prompt to Confirm, Correct, or Skip |
| `/document:render` | Render a document's Dataview code blocks into static markdown tables |
| `/document:lint` | Audit the portfolio for type drift, broken wikilinks, and stale inferred markers, then fix what's safe |

## How it works

1. Run `/document:define` to describe a new document type conversationally
2. The skill asks about fields, sections, relationships, lifecycle, and creation mode
3. It writes a type definition to `.config/documents/types/{name}.md`
4. It generates a complete management skill at `.claude/skills/{name}/SKILL.md`
5. Use the generated `/{name}` command to create, list, get, validate, and transition documents
6. Use `/document:enrich`, `/document:verify-inferred`, `/document:render`, and `/document:lint` to maintain the portfolio over time

## Project structure

```
your-project/
  .config/documents/
    root.md                    # Project manifest (auto-created)
    types/
      brand.md                 # Type definition (you define these)
      brand.skill.md           # Optional sidecar — custom operations and hooks
      prd.md                   # Type definition
  .claude/
    skills/
      brand/SKILL.md           # Generated skill
      prd/SKILL.md             # Generated skill
    commands/
      brand.md                 # Generated command
      prd.md                   # Generated command
```

## Custom logic sidecars

Per-type extensions live next to the type definition as `{name}.skill.md`. They declare extra operations and `pre-{op}` / `post-{op}` hooks that get spliced into the generated skill. See `skills/document-define/references/custom-logic-schema.md`.

## Lifecycle hooks

Type definitions can declare a `## Lifecycle Hooks` section with guards, actions, and notifications per transition. The generated skill enforces guards before status updates, runs actions after, and fires notifications without blocking on failure.

## Hooks

`hooks/hooks.json` wires repository hooks that enforce status transition gates and parent-field inheritance when documents are edited.
