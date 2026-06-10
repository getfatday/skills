# Schema Migrations

The **document schema** is the shape of a project's configuration: the
`root.md` manifest and the type definitions under `.config/documents/types/`.
This file versions that schema and records how to migrate config from one
version to the next.

## Current schema version

**1.**

The plugin declares the version it supports as `documentSchemaVersion` in
`.claude-plugin/plugin.json`. Config files record the version they were
written against in a `schema-version` line — `root.md` in `## Configuration`,
type definitions in `## Identity`. **A config file with no `schema-version`
line is treated as version 1**, so every project that predates versioning
stays valid with no action required.

There are no migration steps yet: version 1 is the baseline. The machinery
below exists so the first breaking schema change has a defined, safe path.

## When the version bumps

- **Additive changes do NOT bump the version.** A new optional field, a new
  optional section, a new optional table — an older type definition still
  generates a valid skill, so no migration is needed. This is the schema's
  long-standing "additive" design principle.
- **Breaking or restructuring changes DO bump the version.** A field renamed
  or removed, a section made required, a table's columns changed, a value
  format changed — anything that makes an older config file generate a wrong
  or broken skill. Each such change increments the version by one and adds a
  migration step below.

## How a migration step is written

Each step is one H2, `## N → N+1`, containing:

1. **What changed** — a one-paragraph description of the breaking change.
2. **Detect** — how to recognize a file still at version `N` (beyond its
   `schema-version` line — e.g. "has a `priority:` field").
3. **Migrate** — an ordered list of deterministic edit instructions that
   transform a version-`N` file into a valid version-`N+1` file, ending with
   updating the `schema-version` line to `N+1`.

Migration steps must be **idempotent** (running a completed step again is a
no-op) and **forward-only** (no down-migrations). A partial failure leaves a
consistent mix of file versions; re-running resumes safely.

Template for the next step (use the concrete numbers when you add it — e.g.
`## 1 → 2` — not the `N` placeholders shown here):

```markdown
## N → N+1

**What changed:** {describe the breaking change}

**Detect:** a `root.md` / type definition whose `schema-version` is `N` or
absent {plus any structural tell}.

**Migrate:**
1. {first edit}
2. {…}
3. Set `schema-version: N+1` in the `## Configuration` / `## Identity` section.
```

## How `/document:upgrade` runs migrations

`/document:upgrade` reads each config file's `schema-version` (absent = 1).
For every version gap between the file and the plugin's
`documentSchemaVersion`, it applies the migration steps in order, then writes
the file back with the bumped `schema-version`. `root.md` and each type
definition migrate independently — a partial run leaves a consistent,
resumable state.

An older plugin encountering a config file with a **higher** `schema-version`
than it supports must warn and proceed read-only — never crash, never
down-migrate.
