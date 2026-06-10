# Factory Contract

The `document` plugin is a **factory plugin**. This document is its contract:
it defines what that means, the rules every feature must follow, and the
classification of every current feature. Read it before adding or changing a
feature.

## What a factory plugin is

A factory plugin is installed by *one* person. It **generates skills,
commands, agents — and sometimes helper scripts — into a repository** as plain
committed files. Those generated files are **materialized artifacts**: they
live in the consuming repo, are committed to git, and are **self-sufficient**.

The defining property:

> Every other contributor — and every tool (Claude Code, Cursor, Codex) — uses
> the materialized artifacts straight from the repo, with **nothing
> installed**. The factory plugin is needed only to *add, change, or upgrade*
> artifacts, never to *use* them.

The benefit: a repository never has missing skills or commands that are
critical to it. The cost: **lifecycle management** — materialized files carry
provenance (which factory, which version produced them), and when the plugin
updates, a repo's copies may need regenerating or migrating.

## Artifact tiers

Every feature produces artifacts in exactly one of three tiers:

- **Tier 1 — Plugin-only.** Lives in the plugin, runs only when the plugin is
  installed. The factory machinery itself.
- **Tier 2 — Operational.** A generic, type-agnostic capability. Classified
  per-feature (below) as **2-plugin** (stays in the plugin) or
  **2-materialized** (copied into the consuming repo).
- **Tier 3 — Per-type generated.** Skills and commands generated for a
  specific document type. Always materialized — they encode *this repo's*
  types and cannot exist anywhere else.

## Materialization criteria

The plugin works at exactly two levels, and the level a feature operates at
decides its tier.

- A **document type** is a *schema*: a type definition
  (`.config/documents/types/{name}.md`), the project manifest (`root.md`), and
  the per-type skill generated from the definition. Types define what
  documents *can exist*.
- A **document instance** is an *actual document* — one file of a given type.

**Scope gate (applied first).** A feature in this plugin MUST operate on
document types or document instances. A feature that operates on *neither* —
a generic transform, a publish/build step, unrelated tooling — **does not
belong in this plugin**. Build it elsewhere. (This is the rule that excludes
a generic dataview-to-markdown renderer: it touches neither types nor
instances.)

**The criterion.**

- A feature that **creates, modifies, or manages document *types*** — the
  definitions, the manifest, the type system, the generated artifacts and
  their lifecycle — is **Tier 1, plugin-only**. Changing the factory's output
  requires the factory.
- A feature that **operates on document *instances*** — creating, reading,
  validating, transitioning, auditing, correcting, enriching, or reporting on
  actual documents — is **materialized**: **Tier 3** if it is generated
  per-type, **Tier 2-materialized** if it is a generic, type-agnostic
  capability.

**Escape hatch.** If an instance-level feature genuinely cannot be made
self-sufficient when materialized — it needs an MCP server, a compiled binary,
credentials, or (like the plugin's hooks) must register with the plugin
runtime — it stays **Tier 2-plugin**. This is rare; prefer materialization.

One-sentence test for a new-feature author:

> Does the feature change *what documents can exist* (type-level →
> **plugin-only**), or does it work with *the documents that already exist*
> (instance-level → **materialized**)? If neither, it does not belong here.

## The self-sufficiency rule

A materialized artifact (Tier 2-materialized or Tier 3) **MUST NOT** reference
`${CLAUDE_PLUGIN_ROOT}` and **MUST NOT** require the plugin to be installed.

If a materialized artifact needs a script, the **script materializes
alongside it** — copied into `.claude/skills/{name}/scripts/` with its own
provenance header — and the artifact references it by a **repo-relative
path**, resolved from the repository root (e.g. via
`$(git rev-parse --show-toplevel)`).

A skill and the scripts it owns are **one atomic unit**: they materialize
together, upgrade together, and never drift apart.

## The provenance stamp

Every materialized artifact records where it came from. One logical stamp,
three serializations.

**Fields:**

| Field | Meaning |
|-------|---------|
| `factory` | the factory plugin name — `document` |
| `factory-version` | the plugin `version` at materialization time (e.g. `0.6.0`) |
| `generated-by` | the generating skill — `document-define` or `document-upgrade` |
| `generator-version` | the generator's internal contract version |
| `source` | path *inside the plugin* the artifact was materialized from |
| `materialized` | ISO date of last materialization |
| `tier` | one of `1-plugin`, `2-plugin`, `2-materialized`, `3` |
| `type-definition` | (Tier 3 only) the type definition that is the source of truth |
| `type-definition-hash` | (Tier 3 only) sha256 of the type-definition file at generation time, so `/document:upgrade` can detect a stale skill when its type definition changed without a plugin-version bump |

**(a) Materialized skills and commands** — YAML frontmatter:

```yaml
factory: document
factory-version: "0.6.0"
generated-by: document-define
generator-version: "1.4"
source: "skills/document-events/SKILL.md"
materialized: "2026-05-22"
tier: 2-materialized
```

**(b) Materialized scripts** — a sentinel-delimited header comment block
between the shebang and the docstring, so `/document:upgrade` can replace it
in place:

```python
#!/usr/bin/env python3
# --- document:provenance ---
# factory: document
# factory-version: 0.6.0
# generated-by: document-upgrade
# source: scripts/derive-events.py
# materialized: 2026-05-22
# tier: 2-materialized
# --- end provenance ---
"""Original module docstring continues here."""
```

**(c) Config files** (`root.md`, type definitions) — config is human-authored,
so it carries **only** a `schema-version` line, not the full stamp (a
`factory`/`materialized` stamp would be a lie — the user owns the file, the
plugin owns the schema). See below.

**Opt-out:** an artifact carrying `provenance: detached` is an intentional
fork. `/document:upgrade` reports it but never regenerates or overwrites it.

## Config schema versioning

`root.md` and type definitions carry a `schema-version`:

- `root.md` — a `schema-version:` line in `## Configuration`.
- type definitions — a `schema-version:` line in `## Identity`.
- **Absent `schema-version` means version 1** (every existing repo is valid).

The plugin declares the schema version it supports in `.claude-plugin/
plugin.json`. Migration steps live in
`skills/document-define/references/schema-migrations.md`, one H2 per version
step (`## 1 → 2`), each an ordered, **idempotent, forward-only** list of edits.

**Additive vs breaking.** A new *optional* field or section is **additive** —
an old type definition still generates a valid skill — and does **not** bump
`schema-version`. Only a **breaking or restructuring** change (a field
renamed, a section made required, a table reshaped) bumps it and requires a
migration step. Most plugin evolution stays migration-free.

## Lifecycle: upgrade and migration

When the factory plugin updates, a repo's materialized artifacts may fall
behind. `/document:upgrade` (Tier 1, plugin-only) brings a repo current:

1. Discovers materialized artifacts by **provenance-stamp scan**.
2. Compares each artifact's versions against the installed plugin.
3. Classifies each: `current`, `stale`, `hand-edited`, `orphan`, `ahead`.
4. Regenerates stale artifacts, re-materializes stale scripts (atomically with
   their skill), runs config schema migrations — reporting a plan first.

Hand-edited artifacts are **never silently overwritten**: `/document:upgrade`
surfaces them for explicit per-file confirmation with a diff.

## Multi-IDE materialization

Materialized artifacts must work in Claude Code, Cursor, and Codex. Every
Tier 2-materialized and Tier 3 artifact is emitted in all three forms into the
consuming repo — `.claude/`, `.cursor/`, and `.github/prompts/` — so no
contributor's tool is left without it.

## Per-feature checklist (for new features)

Every new skill, command, or feature PR must satisfy:

1. **Tier declared.** The feature's `SKILL.md` frontmatter carries a valid
   `tier:` value, justified by the type-vs-instance criterion — and the
   feature passes the scope gate (it operates on types or instances at all).
2. **No plugin leak.** If materialized, the artifact contains no
   `${CLAUDE_PLUGIN_ROOT}` and no `plugins/` path.
3. **Scripts travel with their skill.** If a materialized feature needs a
   script, the script materializes into `.claude/skills/{name}/scripts/` with
   a provenance header, referenced repo-relative.
4. **Schema discipline.** If the feature changes the shape of `root.md` or
   type definitions: additive change → no version bump; breaking change →
   bump `schema-version` and add a `schema-migrations.md` step.
5. **Provenance.** Generated and materialized artifacts carry the full
   provenance stamp.
6. **Multi-IDE.** Materialized artifacts emit Claude / Cursor / Codex forms.

## Current Feature Classification

The audit of every current feature against the criteria above. This table is
living — add a row when a feature is added.

Tier values are the frontmatter `tier:` enum: `1-plugin`, `2-plugin`,
`2-materialized`, `3`. **All `2-materialized` artifacts ship as templates
under `plugins/document/templates/`** — they are not plugin-resident skills.
A consuming repo runs `/document:upgrade` to install them as
repo-local skills + scripts under `.claude/skills/<name>/`, after which
they work with no plugin installed. The factory's runnable surface is only
the Tier-1 commands.

| Feature | Operates on | Tier | Where in the plugin |
|---------|-------------|------|---------------------|
| `document-define` | types | `1-plugin` | `skills/document-define/` — the generator. |
| `document-upgrade` | the type system | `1-plugin` | `skills/document-upgrade/` — the lifecycle command (scan, classify, materialize, regenerate, migrate). |
| `document-lint` | instances | `2-materialized` | `templates/document-lint/` — type-agnostic, no script. |
| `document-verify-inferred` | instances | `2-materialized` | `templates/document-verify-inferred/` — confirms/corrects inferred fields. No script. |
| `document-enrich` | instances | `2-materialized` | `templates/document-enrich/` — backfills relationship fields; ships `enrich.py` alongside. Pairs with `document-verify-inferred`. |
| `document-events` | instances | `2-materialized` | `templates/document-events/` — reports the change history; ships `derive-events.py` alongside. |
| per-type generated skills + commands | instances | `3` | Generated into the consuming repo at `.claude/skills/<type>/` from a user-authored type definition. |
| `hooks/` (`check-document-edit`, `check-lint-write`) | instances | `1-plugin` | `hooks/` — must register with the plugin runtime; the self-sufficiency escape hatch applies. The PreToolUse `check-document-edit.py` enforces type-system integrity at write/edit time without requiring the consuming repo's CLAUDE.md to cooperate (7 guards: direct status/type edits, unknown types, missing required fields/sections, off-lifecycle status, raw Write of typed docs). The PostToolUse `check-lint-write.sh` is advisory only. A no-plugin repo loses these guards (accepted trade-off, below). |
| `document_validator.py` + `.githooks/` pre-commit bundle | instances | `1-plugin` + `2-materialized` (dual-tier) | `scripts/document_validator.py` is the shared guard library. The PreToolUse hook imports it (Tier 1); `/document:upgrade --githooks` *also* materializes it (plus `check-document-staged.py`) into `<repo>/.githooks/` (Tier 2) and wires a one-line invocation into the repo's `.githooks/pre-commit`. The pre-commit enforces G4-G7 at `git commit` time, covering the direct-shell-edit path the PreToolUse hook can't see. Requires the consumer to set `core.hooksPath` once; `/document:upgrade` offers to set it. |
| multi-harness materialization (`target_config.py`, `multi_target_emit.py`, `templates/_root/rulesync.jsonc`) | instances | `1-plugin` (the orchestration) + per-target output is plain on-disk content owned by the consumer | The materializer no longer writes `.cursor/`/`.github/` mirrors directly. It stages canonical content into `.rulesync/skills/<name>/`, then invokes `npx -y rulesync generate --targets <configured> --features skills,commands --simulate-skills --simulate-commands`. Target list is read from `.config/documents/rulesync.jsonc` (defaults: `cursor + codexcli`; the `documentTargets: true` marker distinguishes it from any repo-root `rulesync.jsonc`). **Graceful degradation:** when `npx` is missing, `finalize_targets()` returns `status=deferred` with a structured `fallback_plan`; `/document:upgrade` reads `skills/document-upgrade/references/target-formats.md` and writes each target's mirror by hand (AI fallback). Future `/document:upgrade` runs with Node available restore rulesync as the source of format truth. |
| ~~`document-render`~~ | *neither* | **removed** | Failed the scope gate (touched neither types nor instances). Removed in Phase 2. |

## Accepted trade-offs

- **Frozen-but-functional repos.** A repo with no plugin installed keeps
  working off its materialized artifacts but cannot be upgraded. If the sole
  plugin-owner leaves, the repo freezes at its current version — the
  `factory-version` stamp, committed to git, tells a future contributor
  exactly what to reinstall.
- **Downgrade.** Migrations are forward-only. An older plugin must *tolerate*
  an unknown-higher `schema-version` — warn and proceed — rather than crash.
  `/document:upgrade` refuses to "downgrade-regenerate" an `ahead` artifact.
- **Hooks are plugin-only.** A no-plugin repo loses the PreToolUse type-system
  guards and the PostToolUse advisory lint. Type-system correctness is still
  enforced *eventually* by `/document-lint` and `/document:upgrade` (run
  on-demand by the consumer), but write-time blocking only happens when the
  plugin is installed. The frozen-but-functional contract is preserved: the
  materialized artifacts still work; only the runtime guards relax.
- **Node.js + `npx` is an optional dependency of `/document:upgrade`.** The
  deterministic cross-IDE fanout invokes `npx -y rulesync generate …`. The
  PreToolUse hook, the pre-commit, the materialized skills themselves, and
  every other materialized artifact stay zero-dep. Without Node, the upgrade
  flow falls back to AI-driven per-target generation using the format spec
  in `skills/document-upgrade/references/target-formats.md`. The fallback
  outputs are functionally equivalent but may drift from rulesync's emitted
  format until Node becomes available — re-running `/document:upgrade` then
  restores rulesync output (the source of format truth) atomically.

## What CI enforces — and what it cannot

`scripts/check-factory-contract.py` mechanically verifies: every skill
declares a valid `tier:`; no materialized-tier artifact or template contains
`${CLAUDE_PLUGIN_ROOT}` or a `plugins/` path; every materialized-script
template has a parseable provenance header; `plugin.json` declares a
`documentSchemaVersion` matched by the highest version step in
`schema-migrations.md`. (`documentSchemaVersion` is the plugin-manifest key;
`schema-version` is the per-file key inside `root.md` and type definitions —
they are deliberately distinct names.)

CI **cannot** verify, and these stay human-reviewed: whether a tier
classification is *correct* (the type-vs-instance call can be a judgment for
features that touch both); whether a feature genuinely belongs in the plugin
(the scope gate); whether a materialized skill's prose secretly assumes the
plugin; whether a migration step is truly idempotent; whether a *consuming*
repo's materialized copies are current (CI runs in the plugin repo, not
consumer repos).
