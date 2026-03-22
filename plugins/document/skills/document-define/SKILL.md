---
name: document-define
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

## Conventions
- {project-level conventions}
```

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

**Steps:**

1. **Identify the document type.** Ask via AskUserQuestion:
   - What kind of document is this? (name and display name)
   - One-line description

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
   using the format from type-definition-schema.md.

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

2. **Resolve location.** Read `.config/documents/root.md` to find the
   root type. Read the root type's `## Collections` table. If this type
   is listed, use that path pattern. If not, search all type definitions'
   Collections and Facets tables to find which parent hosts it. If no
   parent hosts it, fall back to `./{DisplayName}/`.

3. **Create skill directory.** `.claude/skills/{name}/`

4. **Generate SKILL.md.** The generated skill file contains:

   ```markdown
   ---
   name: {name}
   description: >
     Manages {display} documents. Handles creation, retrieval, listing,
     validation, and lifecycle transitions.
   generated-by: document-define
   generator-version: "1.2"
   type-definition: ".config/documents/types/{name}.md"
   materialized: "{today}"
   user-invocable: false
   allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion]
   ---
   ```

   The SKILL.md body includes:

   **a. Objective section** — what this skill manages, referencing the type.

   **b. Vault schema section** — generated from the type definition:
   - File ownership pattern (using root document path, not type definition default)
   - Required/optional frontmatter from Fields
   - Required/optional sections from Sections

   **c. Operations section** with these operations:

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
     - Validate the transition against the ALLOWED TRANSITIONS table.
       ONLY listed transitions are permitted. ALL others MUST be rejected.
       Statuses with no outbound transitions are terminal states.
     - If transition is NOT in the allowed list: respond with the error
       message and DO NOT modify the file. Return immediately.
     - ONLY if transition is valid: update the status field.
     - Report the transition: "{name}: {old} -> {new}"
     - If transition is invalid: "Invalid transition: {current} -> {new}.
       Allowed transitions from {current}: {list}."

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

   **d. Dependencies section** — reads_from and consumed_by based on
   relationships.

   **e. Error handling section** — every operation must produce output.
   No silent failures.

5. **Generate template file** (if creation mode includes template).
   Write to `.claude/skills/{name}/templates/{name}.md`:
   - Frontmatter with all required fields as placeholders
   - All required sections as empty H2 headings
   - Optional sections as commented hints

6. **Generate command file.** Write to `.claude/commands/{name}.md`:
   ```markdown
   ---
   name: {name}
   description: Manage {display} documents
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

7. **Create collection directory and index** (if type defines one and it
   doesn't exist yet). Create the directory and index file with empty
   `## Contents` section.

8. **Report.** Confirm what was generated:
   ```
   ## Generated: {display} document type

   **Type definition:** .config/documents/types/{name}.md
   **Skill:** .claude/skills/{name}/SKILL.md
   **Command:** .claude/commands/{name}.md
   **Template:** .claude/skills/{name}/templates/{name}.md (if applicable)
   **Location:** {resolved path from root document}

   Run `/{name} create` to create your first document.
   ```

**Output:** skill path, command path, template path (if any), resolved location.
</generate_operation>

## regenerate — Update a generated skill from its type definition

<regenerate_operation>
**Inputs:** type name or type definition path

**Steps:**

1. **Find the generated skill.** Read `.claude/skills/{name}/SKILL.md`.
   Check the `type-definition` frontmatter field.

2. **Read the current type definition and root document.** Compare paths
   and structure to current generated skill.

3. **Regenerate.** Re-run the `generate` operation. Overwrite the skill,
   template, and command files.

4. **Report diff.** Show what changed:
   - New fields added
   - Fields removed
   - Sections changed
   - Lifecycle transitions changed
   - Creation mode changed
   - Path changed (from root document update)

**Output:** files updated, diff summary.
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
6. Check for `## Collections` and `## Facets` sections in type definition
7. Display as table:

   | Document Type | Description | Location | Skill | Features | Status |
   | {display} | {description} | {path from root} | generated/missing/stale | C (collections), F (facets), H (hosted by parent) | enabled/disabled |

A skill is "stale" if the type definition file is newer than the generated
skill's `materialized` date.

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
   - Empty `## Document Types` section
3. Scan for existing type definitions at `.config/documents/types/*.md`
   and add them to the root with default paths.
4. Report: "Initialized document root for {project}. {N} types registered."

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
