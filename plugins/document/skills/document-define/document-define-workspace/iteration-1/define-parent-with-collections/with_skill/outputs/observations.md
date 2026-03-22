# Observations

## Issues and Ambiguities

### 1. Dual hosting of initiatives and epics

The root type (product-portfolio) already declares initiatives at `./Initiatives/{name}.md` in its Collections table. The new program type also declares initiatives at `./initiatives/{name}.md` (relative to the program directory). This creates two valid locations for initiative documents.

The skill instructions say: "If multiple parent types host this type, ask which parent to use." This covers the create path, but raises questions:
- Does `initiative list` show ALL initiatives across both locations, or only those under a specific parent?
- Does `initiative validate` accept either location as valid?
- Should the root-level initiatives row be removed now that programs host them?

The same issue applies to epics, which are currently hosted by initiatives (in the initiative type's Collections table) AND now by programs.

### 2. No `## Collection` section vs `## Collections` section naming

The task asks to verify "type definition has NO ## Collection section." The schema only defines `## Collections` (plural). There is no `## Collection` (singular) concept in the schema. The type definition correctly uses `## Collections`. This distinction is clear in the schema.

### 3. Collection path pattern uses `{name}` but child types use different key fields

The program's Collections table uses `name` as the key for both initiatives and epics. But the initiative type uses `title` as its name field (not `name`), and the epic type also uses `title`. The key field `name` in the Collections table should match a field in the child type, but neither initiative nor epic has a field literally called `name`. They have `title`.

This is a real conflict. Either:
- The program Collections table should use `title` as the key (matching the child types' fields), or
- The path pattern should use a slug derived from the title, with a convention for how to derive it.

The existing root type uses `name` as the key for initiatives too, so this is a pre-existing issue, not introduced by this task.

### 4. Template creation mode does not specify conversational phases

The user requested "template creation mode." The skill correctly does not generate conversational phases. But the skill instructions (step 6 of define) say to ask about creation mode. Since the user pre-specified "template," no question is needed. The generated type definition correctly uses `mode: template`.

### 5. Program directory structure implies faceted object but type is not declared as one

Programs use `{name}/index.md` as their path (a directory with index.md hub). This matches the "faceted object" pattern from CLAUDE.md. But the program type has no `## Facets` table, meaning no sections can be extracted. This is fine, as not all directory-based types need facets. The directory exists to host child collections, not extractable sections.

### 6. Lifecycle has no initial state convention

The type definition lists transitions but does not specify what status a new document gets. The template defaults to `active`, but a program might start as `paused` or need a `planned` status. The schema does not have a concept of "initial status" or "default status." The template just picks one.

### 7. Skill does not address what happens to child documents when program status changes

When a program moves to `completed`, should child initiatives and epics be validated or transitioned? The skill has no cascade behavior. This is arguably correct (each type manages its own lifecycle), but worth noting as a gap for parent-child relationships.

## Gaps in Skill Instructions

### 8. No guidance on index.md format for collection directories

The skill says "create an index.md in it (empty collection index)" but does not specify the format. Should it have frontmatter? A `## Contents` heading? The CLAUDE.md conventions say "Index files are maps, not content. One link and one sentence per item. Under 30 lines." But the scaffolded index starts empty.

### 9. Registration step ambiguity for hosted types

Step 10 says: "If hosted (will be declared in a parent type's Collections or Facets): add a row to the parent type's Collections or Facets table instead." But the program type IS a parent that hosts collections. It is ALSO a standalone type that needs registration in the root's Collections. The program is standalone (registered in root) AND a parent (hosts initiatives and epics). These are not mutually exclusive, but the instructions present them as an either/or.
