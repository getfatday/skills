---
name: document-enrich
description: >
  This skill should be used whenever the user wants to scan typed
  document instances for missing or legacy-format relationship-field
  values and propose fuzzy-matched replacements. Trigger liberally:
  invoke it when the user mentions enriching or backfilling ANY
  document type's relationship fields (project, parent-task,
  initiative, decision, etc.), normalizing Obsidian-style bare
  wikilinks to canonical piped format, proposing missing links,
  applying confirmed proposals from a YAML file, or finding instances
  whose wikilink fields need repair. Typical phrasings include "enrich
  sessions", "backfill missing project links", "my wikilinks are in
  the old format, normalize them", "propose parent-task matches",
  "scan my epics for missing initiative links", or any request to
  find-and-fix relationship drift across typed documents. Also fires
  on the explicit /document:enrich command. Parameterizes entirely
  over the type's declared links-to relationships — no type or field
  name is hardcoded. Even if the user doesn't say "enrich", invoke
  this skill whenever the task involves proposing link values via
  fuzzy matching or normalizing legacy wikilink formats.
materialized: "2026-04-18"
user-invocable: true
trigger-phrases:
  - "enrich documents"
  - "document enrich"
  - "propose document links"
  - "backfill relationships"
  - "document-enrich"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
---

# document-enrich

<objective>
For any document type with declared `links-to` relationships, scan
instances with missing or legacy-format values and propose matches via
fuzzy-match against candidate target-type instances. The backbone is
`scripts/enrich.py`, parameterized entirely by the type's declared
relationships. Per-type scoring customizations live in
`.config/documents/types/{name}.skill.md` — the generic backbone reads
the sidecar if present; otherwise it uses defaults.
</objective>

## When to Run

- After bulk imports / migrations that leave relationship fields empty
- Periodically to catch stragglers the primary creation hook missed
- When `/document:lint` reports wikilink-integrity breaks (this skill
  repairs them)

## How the Backbone Works

The skill wraps `scripts/enrich.py`. Runtime inputs:

- **Portfolio root** — resolved by walking up from CWD until
  `.config/documents/root.md` is found
- **Type name** — passed as an argument: `/document:enrich <type>`
- **Field name (optional)** — `--field <name>` restricts to a single
  relationship

The script reads:
- `.config/documents/types/{type}.md` — parses `## Fields` and `## Relationships`
- `.config/documents/types/{type}.skill.md` (optional) — reads `## Enrichment`
  overrides: `stopwords`, `score_threshold`, `extra_weight`,
  `skip_fields`
- Instances of every target type referenced by `links-to`

## Operations

### scan — Generate proposals (dry-run, never writes)

**Purpose.** Produce a YAML confirmation file the user can review and edit.

**Steps:**

1. **Resolve portfolio.** Walk up from CWD to find `.config/documents/root.md`.
   If not found, tell the user and exit.
2. **Validate the type.** Ensure `.config/documents/types/{type}.md`
   exists. If not, report and exit.
3. **Run the backbone.**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/document-enrich/scripts/enrich.py \
     --portfolio <portfolio_root> \
     --type <type> \
     [--field <field>]
   ```
4. **Capture stdout** as the proposal file. Show the user a summary:
   - Total proposals
   - High / medium / low / none confidence counts
   - Suggested next step (edit confirmed flags, then run apply)
5. **Write** the proposals to a reviewable file at
   `.config/documents/enrich/{type}-{YYYY-MM-DD}.yaml`.
   Create the `.config/documents/enrich/` directory if absent.
6. **Tell the user** how to edit (`confirmed: false` → `true` per proposal)
   and re-run with apply.

### apply — Apply confirmed proposals

**Purpose.** Walk the proposal file and write confirmed changes to each
instance, setting `inferred: true` on every touched document.

**Steps:**

1. **Locate the proposal file.** Accept it as an argument, or default
   to the most recent file under `.config/documents/enrich/`.
2. **Run the backbone:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/document-enrich/scripts/enrich.py \
     --portfolio <portfolio_root> \
     --apply <proposal_file>
   ```
3. **Report** applied / skipped / created counts. Warn if any apply
   failed (e.g., source file missing).
4. **Follow-up.** Recommend running `/document:verify-inferred --type {type}`
   to review the `inferred: true` markers.

### list-orphans — Report instances whose relationship fields reference missing targets

**Purpose.** Complements `/document:lint`'s wikilink-integrity check
scoped to one type and one relationship.

**Steps:**

1. For the given type, read every instance's frontmatter.
2. For each `links-to` relationship, parse the wikilink target and
   check whether the file exists on disk.
3. Emit a plain report:

   ```
   ## Orphaned {field} links in {type}

   | Instance | Field | Target | Exists? |
   | ... | ... | ... | ... |
   ```

This operation is a pure read — it never writes.

## Per-Type Customization via Sidecar

Consumers extend default scoring by dropping a
`.config/documents/types/{name}.skill.md` with a `## Enrichment` section:

```markdown
## Enrichment

- stopwords: [session, the, a, and, of]
- score_threshold: 40
- skip_fields: [parent-session]
- extra_weight:
    token:portfolio: 20
```

- **`stopwords`** — tokens ignored during matching (noise words in
  filenames)
- **`score_threshold`** — minimum score to generate a proposal
- **`skip_fields`** — relationship fields the scanner should not
  fuzzy-match (e.g., `parent-session` is populated by a creation hook,
  not by inference)
- **`extra_weight`** — per-token bonuses that bias matching toward
  preferred targets (key format: `token:<word>`)

The backbone reads this file; the SKILL.md does not parse it. If the
file is missing, defaults apply.

For worked examples covering stopwords, skip_fields, extra_weight, and
composite configurations, see `references/sidecar-examples.md`.

## Output Contract

The YAML proposal file has one block per inference:

```yaml
proposals:
  - instance_file: Sessions/2026-04-12_asset-cache-core.md
    type: session
    field: project
    current_value: null
    proposed_value: "[[Projects/Egds Asset Cache/index|Egds Asset Cache]]"
    proposed_create: null
    reason: fuzzy_match: token_overlap(asset,cache)
    confidence: high
    confirmed: false  # ← change to true to apply this proposal
```

Fields:

- `instance_file` — path relative to portfolio root
- `type` — the document type scanned
- `field` — the relationship field being inferred
- `current_value` — existing value (null if missing)
- `proposed_value` — canonical wikilink if a match was found
- `proposed_create` — `{target_type}:{name}` if no match but the
  scanner thinks a new target should be created
- `reason` — scoring trace for human inspection
- `confidence` — `high` / `medium` / `low` / `none`
- `confirmed` — user flag; only `true` proposals are applied

## Design Principles

1. **Runtime-parameterized.** The skill takes a type name; all behavior
   follows from the type definition + optional sidecar. No type name
   appears in the skill body.
2. **Review before write.** Scan emits YAML; apply consumes the edited
   YAML. Nothing writes without an explicit `confirmed: true`.
3. **Mark inferences.** Every applied change sets `inferred: true` on
   the touched document so `/document:verify-inferred` can prompt the
   user later.
4. **Idempotent.** Re-running scan after apply skips already-normalized
   values.
5. **Sidecar-scoped customization.** Per-type overrides live alongside
   type definitions and survive plugin regeneration.

<dependencies>
reads_from:
  - .config/documents/root.md (in consuming project)
  - .config/documents/types/{type}.md (type definitions)
  - .config/documents/types/{type}.skill.md (optional overrides)
  - all target-type instances
writes_to:
  - .config/documents/enrich/{type}-{date}.yaml (proposal files)
  - individual instance files (only on --apply with confirmed: true)
consumed_by:
  - document-verify-inferred (drains the inferred queue this skill fills)
  - document-lint (wikilink-integrity rule reports broken targets)
</dependencies>
