---
name: team-member-update
tier: 1-plugin
generator-version: "0.1"
description: "Re-research an existing team-member to incorporate new material — a new book, talk, blog series, or deeper coverage of an area. Merges additively into the existing blueprint, preserves voice, then re-materializes. This is INTELLECTUAL drift, distinct from team-update's file drift."
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
targets: ["*"]
---

# Team Member Update (research-driven enrichment)

This skill is the **intellectual-drift** counterpart to `team-update`. It
re-runs the [research-engine](../team-member-recruit/references/research-engine.md)
on an existing team-member, targeting **net-new material** the member has
published since the blueprint was first generated, then merges the new
findings additively into the blueprint and re-materializes.

Trigger phrasing (natural language):

- "update Kent Beck with his new book Tidy First"
- "enrich Marty Cagan with the Transformed material"
- "deepen Charity Majors on incident response"
- "Kent Beck published Tidy First — pull it into his persona"

It is **not**:

- Bulk file-drift sync — that's `team-update`.
- New member recruitment — that's `team-member-recruit`.
- Catalog re-install — that's `team-member-add`.

## Step 1 — Parse arguments and resolve the target

`$ARGUMENTS` (or the natural-language trigger) typically names:

- **Who** — the team-member by display name or slug
- **What's new** — title of a book / talk / post / topic; possibly multiple

Parse into:

- `target` — the member display name as the user said it
- `new-material` — the user's description of what's new (free text)

Resolve `target` to a slug:

1. **Fast path** — if `target` is already kebab-case and
   `.config/team/team-members/<target>.md` exists, use it directly.
2. **Display-name path** — otherwise list `.config/team/team-members/*.md`
   and match against the `name:` field in each blueprint (case-insensitive,
   exact match first, then unambiguous prefix). If multiple matches,
   `AskUserQuestion` to disambiguate. If no match, refuse and suggest
   `team-member-recruit` for a brand-new member.

If `.config/team/team-members/` doesn't exist, the repo isn't bootstrapped
— refuse and direct the user to `/dream-team:recruit "<name>"`.

## Step 2 — Pre-flight: classify the blueprint's file-drift state

Before doing any research, check whether the materialized artifacts are in
file-drift trouble. Shell out to the scanner:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py" \
    -C "$(git rev-parse --show-toplevel)"
```

The JSON `artifacts[]` array carries `slug` on every entry derived from a
materialized skill or a blueprint. Find the entry where
`slug == <resolved-slug>` AND `kind == "skill"` (the persona skill is the
authoritative classification — the blueprint kind is `config-member` and
only ever classifies on schema drift). Inspect `classification` and
`reason_codes[]`:

| Classification + reason_code | Action |
|------------------------------|--------|
| `current` | Proceed — intellectual update is the right tool. |
| `stale` + `blueprint-hash-drift` only | The user has edited the blueprint by hand. Their edits ARE the intellectual update — re-materialize via `team-update kent-beck` instead of re-researching. Tell the user, route them out. |
| `stale` + `factory-version-drift` (with or without hash drift) | Factory templates have moved. Run `team-update` first to settle file drift, then re-invoke this skill. Tell the user, route them out. |
| `orphan` (reason_code `blueprint-missing`) | Materialized files were deleted. Re-materializing without research is a one-step fix — route to `team-update`. |
| `ahead`, `detached`, `untracked`, `malformed` | Refuse — these are pathological states that team-update is built to surface. |
| `migration-needed` | Schema mismatch. Run `team-update` first, then return here. |

This pre-flight is what makes `/dream-team:update {slug}` work as a single
verb: the slash command runs the same scan, then routes here when
classification is `current`, otherwise to `team-update`.

## Step 3 — Read the existing blueprint

Read `.config/team/team-members/<slug>.md`. Capture, in working memory:

- The `<principles>` list (names + summaries)
- The `<voice>` characterization (framing, metaphors, phrases)
- The `<anti-patterns>` list
- The `<vocabulary>` table (term → meaning)
- The `domains:` array
- Any `<mental-models>` and `<cycle>` sections

Also read any extended references already materialized at
`.claude/skills/<slug>/references/{principles,anti-patterns,vocabulary}.md`
— these expand the blueprint's high-level lists into depth, and the
enrichment may want to add to them too.

## Step 4 — Targeted research (COLLECT, but bounded)

Follow the [research-engine](../team-member-recruit/references/research-engine.md)
methodology, but the COLLECT stage is scoped to the user's `new-material`
description — **not** a re-run of the original survey.

For each piece of new material the user named:

1. WebSearch for the canonical source (book → publisher page +
   chapter summaries / talk → conference page + transcript / blog series
   → index post). Find at least 2 corroborating sources per piece of new
   material when possible.
2. Create research notes under
   `.team-member-workspace/<slug>/research-update-<date>/<source-slug>.md`
   — a fresh subfolder so the update doesn't trample original research.
3. Append a row per new source to a per-update catalog at
   `.team-member-workspace/<slug>/research-update-<date>/sources.md`.

If the user named the topic in the abstract ("deepen Charity Majors on
incident response"), survey what the member has actually published on
that topic since the blueprint was last researched. Use the blueprint's
existing source citations as a "before" baseline; new sources are the
ones the blueprint doesn't already cite.

### Checkpoint

Use `AskUserQuestion`:

> "Found {N} new sources for {member}. Proceed to ANALYZE?"
> - "Proceed (Recommended)"
> - "Add more sources" — user names extra material to research
> - "Cancel"

## Step 5 — Targeted analysis (ANALYZE, but diff-aware)

Read every research note in the per-update folder. Cross-reference
against the existing blueprint dimensions. For each of the six
dimensions, determine the **delta** rather than re-extracting from
scratch:

| Dimension | Diff to compute |
|-----------|-----------------|
| Principles | Net-new principles not already in `<principles>` (deduped by name and meaning) |
| Mental models | Net-new named frameworks |
| Vocabulary | Net-new terms; **also** sharpened definitions for existing terms (flag conflicts!) |
| Anti-patterns | Net-new things the member explicitly warns against |
| Cycle | Has the named process changed? (Most fragile — usually unchanged) |
| Voice | **Almost never changed by an update.** Only update if new material directly contradicts the existing voice — and surface the conflict. |

Write the delta to
`.team-member-workspace/<slug>/research-update-<date>/delta.md` with
sections `## Added principles`, `## Added mental models`, `## Added
vocabulary`, `## Vocabulary conflicts` (existing-term → new-meaning),
`## Added anti-patterns`, `## Cycle changes`, `## Voice notes`. Cite the
new source on every line.

### Conflict resolution

For any **conflicts** (same vocabulary term with a refined or
contradictory meaning, voice contradictions, cycle steps that disagree
with the existing process), use `AskUserQuestion`:

> "`<term>` was defined as `<old>` and the new material says `<new>`.
> Should I replace, keep both as nuances, or skip?"
> - "Replace (Recommended if newer material is definitive)"
> - "Annotate as both" — keep old, note new as refinement
> - "Skip" — preserve existing definition

Default position: **preserve voice and existing meanings unless new
material outright contradicts them**. The existing characterization
came from broader source coverage; new material adds depth, not
overwrites.

## Step 6 — Merge into the blueprint

Edit `.config/team/team-members/<slug>.md` additively:

1. Append new principles to `<principles>` with their source citations.
2. Append new mental models, vocabulary rows, anti-patterns. New
   vocabulary rows sit alongside existing ones — alphabetical order
   within the table.
3. Apply approved conflict resolutions (replace, annotate, or skip).
4. Append a `<recent-material>` block (or extend an existing one) at the
   end of the body that lists the new sources the member now draws on.
   This is what surfaces in the materialized SKILL.md description as
   "recently published on X".
5. Bump `schema-version` only if a schema migration was applied (none
   today — schema is at 1).

Don't reformat the rest of the blueprint. Stable diff = stable provenance
hash for unchanged sections.

## Step 7 — Re-materialize (preserving the enriched blueprint)

Once the blueprint is updated, re-emit the materialized files via the
materializer in **--keep-blueprint** mode. This flag tells the materializer:

- DO NOT overwrite `.config/team/team-members/<slug>.md` from the factory
  template (which would erase Step 6's additive merge).
- DO re-hash the on-disk blueprint and re-stamp the materialized persona
  skill so `blueprint-hash:` matches the enriched content.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --member <slug> --keep-blueprint
```

The materializer:
- Reads the on-disk blueprint (the enriched one).
- Computes its SHA-256, writes it into the persona skill's
  `blueprint-hash:` stamp.
- Refreshes `.claude/skills/<slug>/SKILL.md`, `.cursor/skills/<slug>/SKILL.md`,
  and `.github/skills/<slug>/SKILL.md` together with their `references/`
  (the materializer fans out to all three IDE harnesses by default — Phase 5).
  The Claude form carries the full provenance stamp; the Cursor and Copilot
  mirrors keep only `name:` and `description:` to satisfy their schemas.
- Honors the existing `<extends>` paths to any team-<domain> skill.

If the user added a brand-new domain to the blueprint that has no
corresponding team-<domain> skill, the rewritten `<extends>` will point at
a non-existent file. Detect this by reading the materialized SKILL.md and
checking each `<extends>` target exists at
`.claude/skills/team-<domain>/SKILL.md`. If any target is missing, route
the user to `/dream-team:recruit "<domain>"` to create the team skill —
this skill stays focused on the single member.

## Step 8 — Confirm

Re-scan to confirm `classification: current` for the slug:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py" \
    -C "$(git rev-parse --show-toplevel)" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
        print([a for a in d['artifacts'] \
               if a.get('slug')=='<slug>' and a.get('kind')=='skill'])"
```

Then report:

> Enriched **{Display Name}** ({slug}) with {N} new sources:
> - {source 1 title}
> - {source 2 title}
> - …
>
> Added: {P} principles, {M} mental models, {V} vocabulary terms,
> {A} anti-patterns. Voice preserved.
>
> Re-materialized — `/consult`, `/coach`, `/plan`, `/review` now use the
> enriched persona.

## Completion gates

- Blueprint hash changed (i.e. at least one of the six dimensions actually
  gained content) — a no-op research pass is reported, not committed.
- The pre-existing `<voice>` section is byte-identical unless the user
  approved a voice change in Step 5.
- `upgrade-scan.py` reports `classification: current` for this slug after
  re-materialization.
- The per-update research folder remains on disk — it's the audit trail
  for what was added and from where.

## What this skill does NOT do

- **Add brand-new members.** Use `team-member-recruit` for that. (This
  skill refuses if the target slug isn't already in the roster.)
- **Re-research from scratch.** Original COLLECT/ANALYZE produced the
  blueprint; this is an additive diff. If a user wants a fresh research
  pass (e.g. they distrust the original), remove the member and re-recruit.
- **Resolve file drift.** If the materialized files are stale because of
  factory-version drift or hand edits, the Step 2 pre-flight bounces the
  user to `team-update`.
- **Touch other team-members.** Even when new material name-drops other
  members, this skill stays inside `<slug>` and doesn't edit peers.
