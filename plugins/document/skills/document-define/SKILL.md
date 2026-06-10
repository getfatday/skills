---
name: document-define
tier: 1-plugin
description: >
  Meta-skill that generates document-type-specific skills from type definitions.
  User describes a document type conversationally, document-define produces a
  type definition file and a complete skill for managing documents of that type.
  Generated skills handle lifecycle, relationships, parent-child collections,
  faceted file splitting, and creation modes specific to the document type.
materialized: "2026-03-21"
user-invocable: true
trigger-phrases:
  - "define a new document type"
  - "create a document type"
  - "document-define"
  - "new document type"
  - "add a document type"
  - "define a type"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
targets: ["*"]
---

# document-define

<objective>
Generate document-type-specific skills from type definitions. A type definition
describes what a document type IS (fields, sections, relationships, lifecycle,
creation mode). This skill reads a type definition and generates a complete
skill that manages documents of that type.

Two modes:
1. **Conversational**: User describes a document type. Skill asks clarifying
   questions. Produces a type definition file, then generates the skill from it.
2. **From definition**: User points to an existing type definition file.
   Skill generates (or regenerates) the skill from it.

When packaged as a plugin, commands become `/document:define`, `/document:list-types`, etc.
</objective>

<file_layout>
## Configuration (user-editable, in consuming project)
- **Root document:** `.config/documents/root.md` — project manifest declaring
  which document types exist and where they live in THIS project
- **Type definitions:** `.config/documents/types/{name}.md` — portable
  definitions of what each document type IS

## Generated (by this skill, in consuming project)
- **Skills:** `.claude/skills/{name}/SKILL.md` — per-type skill with CRUD + lifecycle
- **Templates:** `.claude/skills/{name}/templates/{name}.md` — creation template
- **Commands:** `.claude/commands/{name}.md` — per-type command routing

## Reference (bundled with plugin)
- **Schema:** `skills/document-define/references/type-definition-schema.md`
</file_layout>

<root_document>
## Root Document

Every project context has a root document at `.config/documents/root.md`.
It is a thin pointer to the root type — the topmost type in the
document tree.

```markdown
# Document Root

## Configuration
- root-type: {type-name}
- root-location: {path to root document instance, e.g., ./index.md}
- schema-version: 1
- max-fanout: 12        # max handlers invoked per dispatch emit; default 12
- max-depth: 1          # max cascade depth (handler emitting another event); default 1
- max-stubs: 5          # max auto-created stub pages per dispatch invocation; default 5

## Conventions
- naming-convention: Title Case
```

### Schema Version

`schema-version` records which revision of the document schema this project's
config was written against. The current version is **1**. A config file with
no `schema-version` line is treated as version 1 (every pre-existing project
stays valid). When the schema changes in a breaking way, the version is bumped
and a migration step is added to `references/schema-migrations.md`;
`/document:upgrade` runs outstanding migrations. Additive changes (a new
optional field or section) do not bump the version.

`regenerate` never modifies config files — backfilling a missing
`schema-version` line onto a pre-existing `root.md` or type definition is
`/document:upgrade`'s responsibility, not the generator's.

### Dispatch caps

The `max-*` keys are read by `document-dispatch` to cap runaway fan-out,
recursion, and stub creation. They are optional — when absent, dispatch uses
the defaults shown above. Bumping them is fine for portfolios with many
subscribers; lowering them is the right move when a dispatch run starts
feeling chatty.

### Naming Convention

The `naming-convention` field controls how document names become file and
directory names. Supported values: `Title Case` (default), `kebab-case`,
`snake_case`, `PascalCase`, `camelCase`. When not set, default to
**Title Case**. Individual type definitions can override by adding
`naming-convention` to their `## Identity` section.

When resolving paths for document creation, apply the naming convention to
transform the document's name/title field into the filename or directory
name. For example, with `kebab-case`, a document titled "My Feature" would
be created at `my-feature.md` or `my-feature/index.md`.

### Path Resolution
The root type is itself a type definition with a `## Collections` table.
That table declares where all top-level types live — their path patterns,
keys, and indexes. Child types hosted by those top-level types are declared
in THEIR Collections and Facets tables.

Resolution: read root.md → find root type → read its Collections table →
for the requested type, use the path pattern. If the type isn't in the
root's Collections, check all type definitions' Collections tables to find
which parent hosts it. If no parent hosts it, fall back to `./{DisplayName}/`.

Type definitions do not declare locations. They describe document shape only.
Location flows top-down through the tree: root type → its Collections →
child types → their Collections → and so on.

### Auto-Registration
When `document-define` creates a new standalone type definition, it adds
a row to the root type's `## Collections` table. When creating a hosted
type, it adds a row to the parent type's Collections table instead.
If no root document exists, create one with a new root type named after
the project directory.
</root_document>

<operations>

## define — Create a new document type (conversational)

<define_operation>
**Inputs:** type name (optional — can be discovered through conversation)

**Optional integration:** if the `dream-team` plugin is installed, step 1a
offers an avatar consult that can propose starter fields / sections /
lifecycle based on the type's purpose. It's purely additive — the skill
works identically when the plugin is absent.

**Steps:**

1. **Identify the document type.** Ask via AskUserQuestion:
   - What kind of document is this? (name and display name)
   - One-line description

1a. **(Optional) Dream-team consult.** After identity is captured,
   offer the user a quick avatar consult to expand the type's fields
   and sections before formalizing them. This step is OPTIONAL and
   requires the `dream-team` plugin. If the plugin is not installed
   (no `/dream-team:consult` command discoverable), skip silently and
   proceed to step 2.

   If available, prompt:
   - "Want to consult the dream-team on this type's fields / sections /
     lifecycle before writing it? (Yes / No)"
   - If Yes: pick 2–4 relevant avatars. Either ask the user to choose
     or auto-select based on the type's purpose:
     - Work / engineering-adjacent types → engineering, management, operations
     - Product / planning types → product, management, operations
     - Personal-ops / knowledge types → personal-finance, growth, operations
     - Mixed / general → ask the user to pick
   - Invoke `/dream-team:consult` with:
     - `question: "Design the fields, sections, and lifecycle for a
       {display} document type. What must it carry? What relationships
       does it have? What lifecycle states?"`
     - `avatars: [selected list]`
     - Pattern: `map-reduce` (each avatar answers independently; a
       synthesis pass merges)
   - Synthesize the response into a proposed fields + sections +
     lifecycle spec. Present to the user as a draft.
   - Ask: "Accept these as starting fields/sections? (Accept all /
     Pick & choose / Start from scratch)"
   - Fold the accepted items into the conversational state so steps
     2-6 treat them as user-confirmed.

   The consult is conversational, not a contract — the user can edit
   or override anything. If `/dream-team:consult` errors or times out,
   fall back to the standard conversational flow and report the
   failure without blocking.

2. **Fields.** Ask:
   - What information goes in the frontmatter?
   - For each field: name, type, required or optional
   - Suggest `type`, `created`, and `status` as defaults

3. **Sections.** Ask:
   - What sections does the document body have?
   - Which are required vs optional?
   - Brief description of expected content for each

4. **Relationships.** Ask:
   - Does this document type link to other types? Which ones, via which field?
   - Do other types link back to this one?

5. **Lifecycle.** Ask:
   - What statuses can this document have?
   - What transitions are valid? (e.g., draft -> review -> approved)

6. **Creation mode.** Ask:
   - How should new documents be created?
     - **Template**: stamp a file with empty sections, user fills in
     - **Conversational**: multi-phase interview that builds the document
     - **Both**: template for quick creation, conversational for guided creation
   - If conversational: what phases? What does each phase gather?

7. **Collections.** Ask:
   - "Does this type host collections of other document types within its directory?"
   - If yes, for each collection gather:
     - What type of documents? (must be a defined type or planned type)
     - What field is the key/identifier? (a field from the child type)
     - What's the relative path? (e.g., `./stories/{key}.md`)
   - Write `## Collections` table to the type definition.

8. **Facets.** Ask:
   - "Can sections of this document be extracted into sibling files when it gets too large?"
   - If yes, for each facet gather:
     - Which section heading? (must be an H2 section from the Sections list)
     - What filename when extracted? (e.g., `./strategy.md`)
     - What document type is the extracted file? (must match a type definition)
   - Write `## Facets` table to the type definition.

9. **Write type definition.** Write to `.config/documents/types/{name}.md`
   using the format from type-definition-schema.md. Include
   `schema-version: 1` in the `## Identity` section.

10. **Register the type.** A type can be registered in multiple places:
   - Ask: "Where should documents of this type live?"
   - For each location:
     - Ask for the path pattern (e.g., `./Brands/{name}.md`)
     - Ask which field(s) form the key/filename
     - Determine which parent hosts this location:
       - If it's a root-level collection: add a row to the root type's
         `## Collections` table
       - If it's nested under another type: add a row to that parent
         type's `## Collections` or `## Facets` table
   - A type can be both root-level AND hosted by parents. Both are valid.
   If no root document exists, create one with a new root type.

11. **Generate skill.** Run the `generate` operation on the new type definition.

**Output:** type definition path, root document updated, generated skill path.
</define_operation>

## generate — Generate a skill from a type definition

<generate_operation>
**Inputs:** type name or type definition path

**Steps:**

1. **Read the type definition.** Find at `.config/documents/types/{name}.md`.
   Parse all sections.

2. **Check for custom logic sidecar.** Look for `.config/documents/types/{name}.skill.md`. If present, parse per `references/custom-logic-schema.md`:
   - Parse `## Operations` H2 and its H3 children as extra operations.
   - Parse `## Hooks` H2 and its H3 children as `pre-{op}` / `post-{op}` hooks.
   - Parse `## Subscriptions` H2 as a markdown table with rows of (event, handler, condition).
     - Validate `event` against the reserved event names listed in `skills/document-dispatch/references/event-schema.md` (`document-created`, `document-updated`, `link-created`, `entity-mentioned`, `lifecycle-changed`). Reject unknown events with file path + row number.
     - Validate `condition` against the closed grammar (`always` | `<field> <op> <literal>` | `<field> in {<lit>, ...}`). Reject parse failures with file path + row number, BEFORE writing any files.
     - Resolve `handler`: a handler that names a default op or a sidecar-declared extra op reuses that block; a handler that doesn't exist becomes a stub op.
   - Validate per the spec's Error Cases. Abort generation on any error (unknown H2 warns only).
   - Hold the parsed sidecar for use in step 5 (SKILL.md generation) and step 7 (command file).
   If no sidecar exists, proceed with default generation. This is not an error.

3. **Resolve location and naming convention.** Read `.config/documents/root.md`
   to find the root type and the `naming-convention` from `## Conventions`
   (default: `Title Case`). Check if the type definition overrides the
   convention in its `## Identity` section. Read the root type's
   `## Collections` table. If this type is listed, use that path pattern.
   If not, search all type definitions' Collections and Facets tables to
   find which parent hosts it. If no parent hosts it, fall back to
   `./{DisplayName}/`. Apply the naming convention when resolving
   `{field-name}` placeholders in path patterns.

4. **Create skill directory.** `.claude/skills/{name}/`

5. **Generate SKILL.md.** The generated skill file contains:

   ```markdown
   ---
   name: {name}
   description: >
     Manages {display} documents. Handles creation, retrieval, listing,
     validation, and lifecycle transitions.
   factory: document
   factory-version: "{plugin-version}"
   generated-by: document-define
   generator-version: "1.4"
   source: "skills/document-define/SKILL.md"
   type-definition: ".config/documents/types/{name}.md"
   type-definition-hash: "{sha256-of-type-definition}"
   materialized: "{today}"
   tier: 3
   user-invocable: false
   allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion]
   ---
   ```

   This frontmatter block is the artifact's **provenance stamp** (see the
   plugin's `FACTORY.md`). Set `factory-version` to the `version` field from
   the plugin's `.claude-plugin/plugin.json` at generation time;
   `type-definition` is the source of truth this Tier-3 skill is regenerated
   from; `type-definition-hash` is the sha256 of the type-definition file's
   bytes at generation time, computed with the equivalent of `sha256sum
   .config/documents/types/{name}.md` — `/document:upgrade` compares it
   against the current type-definition's hash to detect a stale skill when
   its type changed without a plugin-version bump. `tier: 3` marks it as a
   per-type generated artifact. Bump `generator-version` here whenever the
   generation rules below change.

   The SKILL.md body includes:

   **a. Objective section** — what this skill manages, referencing the type.

   **b. Vault schema section** — generated from the type definition:
   - File ownership pattern (using root document path, not type definition default)
   - Required/optional frontmatter from Fields
   - Required/optional sections from Sections

   **c. Lifecycle hooks section** — (only for types with `## Lifecycle Hooks`).
   Generate a LIFECYCLE HOOKS section in the skill listing guards, actions,
   and notifications per transition. Expand wildcards: if the type definition
   declares `* -> abandoned` and the transitions list includes `active -> abandoned`
   and `paused -> abandoned`, emit both specific transitions in the generated
   hooks table. Specific transitions from the type definition take precedence
   over wildcards when both match the same from/to pair.

   Format in the generated skill:

   ```markdown
   ## Lifecycle Hooks

   ### Guards
   | Transition | Condition | On Failure |
   |------------|-----------|------------|
   | active -> completed | all steps done or skipped | "Not all steps are complete." |
   | active -> completed | skill: branch-engine codeowners-check | (skill reports reason) |

   ### Actions
   | Transition | Description | Skill |
   |------------|-------------|-------|
   | draft -> active | create git branch and draft PR | branch-engine create-worktree |

   ### Notifications
   | Transition | Description |
   |------------|-------------|
   | active -> completed | update parent initiative progress |
   | paused -> completed | update parent initiative progress |
   ```

   **d. Operations section** with these operations:

   - **store** — Store a document with pre-built content. This is the
     primary creation path when an expert agent (dream-team avatar or
     other facilitator) has already produced the content.
     - Input: frontmatter fields and section content (structured).
     - **Resolve location:** Check if any parent type declares this type
       in its `## Collections` table (glob `.config/documents/types/*.md`,
       look for Collections tables referencing this type name). If found,
       ask which parent document this belongs to (e.g., "Which product?")
       and resolve the path using the parent's collection path pattern.
       If multiple parent types host this type, ask which parent to use.
       If no parent hosts this type, check the root type's Collections.
       If not there either, use the flat default `./{DisplayName}/`.
     - Write the document with provided frontmatter and sections.
     - If the type has `## Collections`: scaffold collection subdirectories.
     - After creation: update collection index, validate links.
     - Always end with a confirmation message.

   - **create** — Create a new document interactively. Fallback for
     when no expert agent is driving the conversation.
     - **Resolve location:** Same as store.
     - If creation mode is `template`: stamp a file from the template,
       prompt user for required fields, write to the resolved location,
       update index if applicable.
     - If creation mode is `conversational`: walk through the defined
       phases, gathering content for each section, then write the
       complete document. Note: the conversational phases in the type
       definition document what an expert agent would gather. The create
       operation uses them as a basic interview guide. For richer
       facilitation, use an expert agent that calls `store` instead.
     - If the type has `## Collections`: scaffold collection subdirectories.
       For each declared collection, create the subdirectory if it doesn't
       exist and create an index.md in it (empty collection index).
     - After creation: update collection index. If the type has
       `links-to` relationships, validate that linked documents exist.
       If linked types have `linked-from` declarations, update the
       linked document's backlink field.
     - Always end with a confirmation message listing: file created,
       fields set, relationships linked, index updated, collections
       scaffolded (if any).

   - **get** — Read and display a document by name or path.
     - Output the document's frontmatter summary and section headings.
     - If the type has `## Collections`: for each declared collection,
       glob the collection path and show a summary line with count and
       links to child documents.
     - Always produce output, even if not found (error message).

   - **list** — List all documents of this type.
     - Read the collection index if it exists, or glob the collection location.
     - Display as a table: name, status, created date, key relationships.
     - If the type has `## Collections`: include a column showing child
       collection counts (e.g., "3 stories, 2 experiments").
     - If no documents exist, say so explicitly.

   - **validate** — Validate a document against the type definition.
     - Check required frontmatter fields are present and correctly typed.
     - Check required sections exist.
     - Check enum fields have valid values.
     - Check relationship links point to existing documents.
     - If any parent type hosts this type in its `## Collections` table:
       check that documents of this type actually reside under a valid
       parent document's directory. To verify: glob parent type's
       collection location and confirm this document's path matches.
     - If the type has `## Facets`: check the hub file size against
       150-line limit. If over limit, suggest which facets could be
       extracted. If facets are already extracted (link exists in hub),
       verify the sibling files exist and are valid documents of the
       declared type.
     - Report pass/fail per field and section with specific error messages.
     - Always produce output.

   - **update-status** — Transition a document's lifecycle status.
     1. Read current status from frontmatter.
     2. Validate the transition against the ALLOWED TRANSITIONS table.
        ONLY listed transitions are permitted. ALL others MUST be rejected.
        Statuses with no outbound transitions are terminal states.
        If transition is NOT in the allowed list: respond with
        "Invalid transition: {current} -> {new}. Allowed transitions
        from {current}: {list}." and DO NOT modify the file. Return.
     3. **Run guards** for this transition (if any in LIFECYCLE HOOKS).
        Evaluate each guard in declaration order.
        - Inline guards: read the document and check the condition.
          If the condition is not met, reject with the failure message.
        - Skill guards: invoke the referenced skill. If it returns
          failure, reject with its reason.
        - If ANY guard fails: report "Guard failed: {failure message}"
          and DO NOT modify the file. Return.
     4. Update the status field in frontmatter.
     5. **Run actions** for this transition (if any in LIFECYCLE HOOKS).
        Execute each action's referenced skill in declaration order.
        If an action fails, the transition stands — report the failure
        but do NOT roll back: "Status updated to {new}. Action
        '{description}' failed: {reason}."
     6. **Run notifications** for this transition (if any in LIFECYCLE
        HOOKS). Fire each notification. Never block on failure.
     7. Report the transition: "{name}: {old} -> {new}" with any
        action results or failures.

     When the type definition has no `## Lifecycle Hooks` section,
     skip steps 3, 5, and 6 — validate and update only.

   - **split** — (Only for types with `## Facets`.) Extract a section
     to a sibling file.
     - Input: document name, section name.
     - Look up the section in the type's `## Facets` table to find
       the target file path and document type.
     - Read the hub document. Find the `## {section}` heading.
     - Extract the section content (everything from H2 to next H2 or EOF).
     - Create the sibling file with proper frontmatter (type from
       Facets table, plus any required fields for that type).
     - Replace the section in the hub with: `See [{Section}](./{file})`.
     - Save both files.
     - Report: "Extracted ## {section} to {file} ({type} document)."

   - **merge** — (Only for types with `## Facets`.) Inline a sibling
     file back into the hub.
     - Input: document name, section name.
     - Read the hub document. Find the link to the facet file.
     - Read the facet file content (strip frontmatter).
     - Replace the link line with the full section content as an H2.
     - Delete the facet file.
     - Save the hub.
     - Report: "Merged {file} back into ## {section}."

   - **Extra operations from sidecar.** For each H3 under the sidecar's `## Operations`, append a new `<{op-name}_operation>` block inside the `<operations>` section, after all default blocks, in the order declared in the sidecar. The block body is copied verbatim from the sidecar.

   - **Splice hooks into default operations.** For each H3 under the sidecar's `## Hooks`:
     - Parse as `{pre|post}-{target-op}`. The target-op must be a default op or a sidecar-declared extra op.
     - Locate the target operation block in the generated SKILL.md.
     - For `pre-{op}`: insert the hook body immediately before the `**Steps:**` list, prefixed with a `**Pre-hook:**` label. Concatenate multiple pre-hooks under one label in file order.
     - For `post-{op}`: insert the hook body immediately after the Steps list and before `**Output:**`, prefixed with a `**Post-hook:**` label. Concatenate multiple post-hooks under one label in file order.
     - Copy hook bodies verbatim.

   - **Splice subscription handlers + subscriptions block.** For each row under the sidecar's `## Subscriptions`:
     - If the `handler` names a default op or a sidecar-declared extra op (from `## Operations`), reuse that op — do NOT generate a new block. Subscription wiring is handled at dispatch time by the `<subscriptions>` block (see below), not by per-handler blocks.
     - If the `handler` is otherwise undeclared, append a new `<{handler}_operation>` block to the `<operations>` section AFTER all default blocks AND after all sidecar-declared extra-op blocks, in declaration order. Body:

       ```markdown
       ## {handler} — Stub handler for subscribed events.

       <{handler}_operation>
       **Inputs:** event payload (JSON on stdin).

       **Steps:**

       1. # TODO: implement {handler} — payload schema documented in skills/document-dispatch/references/event-schema.md.

       **Output:** describe the side effect.
       </{handler}_operation>
       ```

     - After the closing `</operations>` tag, append a sibling `<subscriptions>` block listing the type's subscriptions in source order:

       ```markdown
       <subscriptions>
       ## Subscriptions

       | event              | handler            | condition |
       |--------------------|--------------------|-----------|
       | entity-mentioned   | log-mention        | always    |
       </subscriptions>
       ```

     - The `<subscriptions>` block exists so `/{type}` users can see at a glance which events the skill listens to. `document-dispatch` reads the sidecar table directly — it does NOT depend on this rendered block.
     - When the sidecar has no `## Subscriptions` section, NO `<subscriptions>` block is written and NO stub handler operations are generated. Generated output for a type without subscriptions is byte-identical to the v0.5.1 baseline.

   **e. Dependencies section** — reads_from and consumed_by based on
   relationships.

   **f. Error handling section** — every operation must produce output.
   No silent failures.

6. **Generate template file** (if creation mode includes template).
   Write to `.claude/skills/{name}/templates/{name}.md`:
   - Frontmatter with all required fields as placeholders
   - All required sections as empty H2 headings
   - Optional sections as commented hints

7. **Generate command file.** Write to `.claude/commands/{name}.md`. It
   carries the same provenance stamp as the generated skill:
   ```markdown
   ---
   name: {name}
   description: Manage {display} documents
   factory: document
   factory-version: "{plugin-version}"
   generated-by: document-define
   generator-version: "1.4"
   source: "skills/document-define/SKILL.md"
   type-definition: ".config/documents/types/{name}.md"
   type-definition-hash: "{sha256-of-type-definition}"
   materialized: "{today}"
   tier: 3
   allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion]
   ---

   Route to `.claude/skills/{name}/SKILL.md` operations:
   - `/{name} store` → store operation (for expert agent handoff)
   - `/{name} create` → create operation (interactive fallback)
   - `/{name} list` → list operation
   - `/{name} get {identifier}` → get operation
   - `/{name} validate` → validate operation
   - `/{name} status {identifier} {new-status}` → update-status operation
   ```

   If the type has `## Facets`, add these routes:
   ```markdown
   - `/{name} split {identifier} {section}` → split operation
   - `/{name} merge {identifier} {section}` → merge operation
   ```

   For each extra operation declared in the sidecar's `## Operations`, add a route:
   ```markdown
   - `/{name} {op-name}` → {op-name} operation
   ```

   For each subscription handler that became a stub op (i.e., the handler name is not a default op and not declared in `## Operations`), add a route:
   ```markdown
   - `/{name} {handler}` → {handler} operation (subscription stub)
   ```

   Subscription handlers that reuse a default op or a sidecar-declared extra op do NOT add a new route — they reuse the existing route.

8. **Create collection directory and index** (if type defines one and it
   doesn't exist yet). Create the directory and index file with empty
   `## Contents` section.

9. **Cross-IDE fanout.** Shell out to the materializer's
   `--post-generate` mode, which stages the just-generated Tier-3
   skill + command from `.claude/skills/{name}/` and
   `.claude/commands/{name}.md` into `.rulesync/skills/{name}/` and
   `.rulesync/commands/{name}.md`, then invokes
   `npx -y rulesync generate` with the targets configured in
   `.config/documents/rulesync.jsonc`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
     -C <repo> --post-generate {name}
   ```

   Three possible statuses (same shape as the Tier-2 path):

   - **`ok`** — rulesync ran. `.cursor/skills/{name}/`,
     `.codex/skills/{name}/`, and any other configured target's
     output is on disk. Done.
   - **`failed`** — rulesync exited non-zero. Surface stderr;
     decide with the user whether to retry or AI-fallback.
   - **`deferred`** — `npx` isn't on PATH. **AI fallback:** read
     `${CLAUDE_PLUGIN_ROOT}/skills/document-upgrade/references/target-formats.md`
     and for each target in `fanout.targets`, write
     `<target-dir>/skills/{name}/SKILL.md` and the appropriate
     per-target command file by hand, applying the documented
     frontmatter rules. Same procedure as the Tier-2 path
     (`/document:upgrade` step 5.8).

   This step makes Tier-3 generation a single command: the new type's
   skill appears in every configured harness without requiring the
   user to remember to run `/document:upgrade` afterwards.

10. **Report.** Confirm what was generated:
    ```
    ## Generated: {display} document type

    **Type definition:** .config/documents/types/{name}.md
    **Skill:** .claude/skills/{name}/SKILL.md
    **Command:** .claude/commands/{name}.md
    **Template:** .claude/skills/{name}/templates/{name}.md (if applicable)
    **Location:** {resolved path from root document}
    **Custom logic:** sidecar present (N extra ops, M hooks, K subscriptions) | no sidecar
    **Cross-IDE mirrors:** cursor, codexcli (or whatever rulesync.jsonc lists) | AI-fallback if npx missing

    Run `/{name} create` to create your first document.
    ```

    The confirmation prose must report sidecar presence and what was spliced (extra operations appended, pre/post hooks added to which target operations, subscriptions registered with which events, stub handler operations generated for any subscription handlers that didn't already exist), plus which targets received output through rulesync vs the AI fallback.

**Output:** skill path, command path, template path (if any), resolved location, fanout status.
</generate_operation>

## regenerate — Update a generated skill from its type definition

<regenerate_operation>
**Inputs:** type name or type definition path

**Steps:**

1. **Find the generated skill.** Read `.claude/skills/{name}/SKILL.md`.
   Check the `type-definition` frontmatter field.

2. **Read the current type definition, sidecar, and root document.** Also read `.config/documents/types/{name}.skill.md` if it exists — always reload fresh, never preserve manual edits to the generated SKILL.md. Compare paths and structure to current generated skill.

3. **Regenerate.** Re-run the `generate` operation. Overwrite the skill,
   template, and command files. **Preserve `materialized`:** if a newly
   generated file is identical to the existing one in every line except its
   `materialized:` provenance date, keep the existing file's `materialized`
   value. This keeps a no-op regeneration byte-identical, and makes
   `materialized` mean "date of last actual change" — which `list-types`
   staleness and `/document:upgrade` drift detection rely on.

4. **Cross-IDE fanout.** Re-running generate (step 3) already includes
   its own step 9 (`--post-generate`), so the configured cross-IDE
   targets are refreshed automatically. No additional invocation is
   needed here. The fanout status flows through into the diff
   report.

5. **Report diff.** Show what changed:
   - New fields added
   - Fields removed
   - Sections changed
   - Lifecycle transitions changed
   - Lifecycle hooks changed (guards/actions/notifications added, removed, or modified)
   - Sidecar added / removed
   - Sidecar extra operations added or removed
   - Sidecar hooks added or removed
   - Sidecar subscriptions added, removed, or changed (event, handler, or condition)
   - Stub handler operations generated, removed, or renamed
   - Creation mode changed
   - Path changed (from root document update)
   - Cross-IDE mirrors refreshed (which targets, via rulesync or AI fallback)

**Output:** files updated, diff summary, fanout status.
</regenerate_operation>

## list-types — Show all defined document types

<list_types_operation>
**Steps:**

1. Read root document at `.config/documents/root.md` to find the root type.
2. Glob `.config/documents/types/*.md`
3. For each type, read the Identity section (name, display, description)
4. Check if a generated skill exists at `.claude/skills/{name}/SKILL.md`
5. Resolve location: check root type's Collections table, then parent
   types' Collections/Facets tables, then flat default
6. Check for `## Collections` and `## Facets` sections in type definition. Check for sidecar at `.config/documents/types/{name}.skill.md`.
7. Display as table:

   | Document Type | Description | Location | Skill | Features | Custom Logic | Status |
   | {display} | {description} | {path from root} | generated/missing/stale | C (collections), F (facets), H (hosted by parent) | yes (N ops, M hooks, K subs) / no | enabled/disabled |

A skill's "stale" flag is whatever `/document:upgrade` would assign — a
mismatch in `factory-version`, `generator-version`, or the recorded
`type-definition-hash` against the current type-definition file. To compute
it, shell out to `${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py -C <repo>`
and use its classification; this is the same comparator
`/document:upgrade` uses, so `list-types` and `/document:upgrade` never
disagree about which skills are stale. (The older mtime-based check was
replaced because it broke after a fresh `git clone` or `git checkout`.)

**Output:** type count, generated count, stale count.
</list_types_operation>

## init — Create a root document for this project

<init_operation>
**Inputs:** project name (optional — defaults to directory name)

**Steps:**

1. Check if `.config/documents/root.md` already exists. If so, report
   and exit.
2. Create `.config/documents/root.md` with:
   - Project identity from directory name or provided name
   - A `## Configuration` section seeded with `root-type`, `root-location`,
     `schema-version: 1`, and dispatch caps `max-fanout: 12`, `max-depth: 1`,
     `max-stubs: 5` (defaults; user can edit them later)
   - `## Conventions` section with `naming-convention: Title Case`
   - Empty `## Document Types` section
3. Scan for existing type definitions at `.config/documents/types/*.md`
   and add them to the root with default paths.
4. Report: "Initialized document root for {project}. {N} types registered. Dispatch caps seeded with defaults (max-fanout=12, max-depth=1, max-stubs=5)."

**Output:** root document path, types registered count.
</init_operation>

</operations>

<skill_boundaries>
| Concern | Owner |
|---------|-------|
| Type definition format and schema | **document-define** (this skill) |
| Root document and path resolution | **document-define** (this skill) |
| Skill generation from type definitions | **document-define** (this skill) |
| Generated skill behavior (CRUD, lifecycle) | **Generated skill** (per-type) |
| Collection structure and indexes | **vault-structure** (structural rules) |
</skill_boundaries>

<dependencies>
reads_from:
  - .config/documents/types/*.md (type definitions, in consuming project)
  - .config/documents/root.md (project root document, in consuming project)
  - skills/document-define/references/type-definition-schema.md (schema reference, bundled with plugin)
consumed_by:
  - generated skills (produced by this skill, written to consuming project)
  - generated commands (produced by this skill, written to consuming project)
note: Generated skills for hosted types read sibling type definitions
  during creation (to find which parent types host them) and during
  validation (to verify parent's Collections table). This is a
  cross-type-definition read at create and validate time.
</dependencies>

<error_handling>
- If type definition has missing required sections, report which are missing
  and offer to fill them conversationally.
- If a type name conflicts with an existing skill, warn and ask before overwriting.
- If collection location conflicts with another type, warn.
- If relationship references a type that doesn't have a type definition, warn
  but proceed (the linked type may be defined later).
- If a Collections table references a child type that doesn't have a type
  definition, warn but proceed (the child type may be defined later).
- If a document lives under a parent directory but the parent type's
  Collections table doesn't declare this child type, warn during validate.
- If a Facets table references a section heading that doesn't exist in the
  type's Sections list, error — the section must be defined before it can
  be declared as extractable.
- If split is called on a section not listed in the Facets table, error
  with: "Section '{name}' is not declared as a facet. Declared facets: {list}."
- If no root document exists during generate, create one automatically.
- Never generate a skill silently. Always report what was created.
</error_handling>
