# Factory Contract

The `dream-team` plugin is a **factory plugin**. This document is its contract:
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
> team-members and team workflow, never to *consult, coach, plan, or review*
> with them.

The benefit: a repository never has a missing team workflow or an inaccessible
team-member when the plugin author is away. The cost: **lifecycle management**
— materialized files carry provenance (which factory, which version produced
them), and when the plugin updates, a repo's copies may need regenerating or
migrating.

## Artifact tiers

Every feature produces artifacts in exactly one of three tiers:

- **Tier 1 — Plugin-only.** Lives in the plugin, runs only when the plugin is
  installed. The factory machinery itself.
- **Tier 2 — Operational.** A generic, team-agnostic capability. Classified
  per-feature (below) as **2-plugin** (stays in the plugin) or
  **2-materialized** (copied into the consuming repo).
- **Tier 3 — Per-team-member generated.** Skills generated for a specific
  team-member or team. Always materialized — they encode *this repo's*
  roster and cannot exist anywhere else.

## Materialization criteria

The plugin works at exactly two levels, and the level a feature operates at
decides its tier.

- A **team-member** is a *persona*: a blueprint
  (`.config/team/team-members/{slug}.md`), the roster manifest
  (`.config/team/root.md`), and the per-member skill generated from the
  blueprint. Members define *who can speak in a consultation*.
- A **consultation** is an *actual run* — one execution of the team workflow
  against a question, plan, code review, or coaching topic.

**Scope gate (applied first).** A feature in this plugin MUST operate on
team-members (or the team structures that group them — domain teams and the
roster manifest) or on consultations. A feature that operates on *neither* —
a generic notebook, a publish/build step, unrelated tooling — **does not
belong in this plugin**. Build it elsewhere.

**The criterion.**

- A feature that **creates, modifies, or manages team-members or teams** —
  blueprints, the roster manifest, the persona-generation pipeline, the
  generated artifacts and their lifecycle — is **Tier 1, plugin-only**.
  Changing the factory's output requires the factory.
- A feature that **operates on consultations** — discovering the roster,
  selecting a team, picking a conversation pattern, coordinating teammates,
  synthesizing findings — is **materialized**: **Tier 3** if it is generated
  per-member, **Tier 2-materialized** if it is a generic, team-agnostic
  capability (the team-assemble engine, the orchestrator agent, the 4 entry
  commands).

**Escape hatch.** If a consultation-level feature genuinely cannot be made
self-sufficient when materialized — it needs an MCP server, a compiled binary,
credentials, or (like the plugin's hooks) must register with the plugin
runtime — it stays **Tier 2-plugin**. This is rare; prefer materialization.

One-sentence test for a new-feature author:

> Does the feature change *who can be on the team* or *what shape a team-member
> takes* (member-level → **plugin-only**), or does it work with *the
> team-members that already exist* (consultation-level → **materialized**)? If
> neither, it does not belong here.

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

The 10 conversation patterns are part of `team-assemble`'s materialized
bundle, living under `.claude/skills/team-assemble/patterns/`. The orchestrator
agent reads them via repo-relative path from the team-assemble skill — never
from a plugin path.

## The provenance stamp

Every materialized artifact records where it came from. One logical stamp,
three serializations.

**Fields:**

| Field | Meaning |
|-------|---------|
| `factory` | the factory plugin name — `dream-team` |
| `factory-version` | the plugin `version` at materialization time (e.g. `0.5.0`) |
| `generated-by` | the generating skill — `team-member-recruit`, `team-update`, or `team-member-add` |
| `generator-version` | the generator's internal contract version |
| `source` | path *inside the plugin* the artifact was materialized from |
| `materialized` | ISO date of last materialization |
| `tier` | one of `1-plugin`, `2-plugin`, `2-materialized`, `3` |
| `blueprint` | (Tier 3 only) the blueprint that is the source of truth |
| `blueprint-hash` | (Tier 3 only) sha256 of the blueprint file at generation time, so `/dream-team:update` can detect a stale skill when its blueprint changed without a plugin-version bump |

**(a) Materialized skills, commands, and agents** — YAML frontmatter:

```yaml
factory: dream-team
factory-version: "0.5.0"
generated-by: team-member-recruit
generator-version: "1.0"
source: "templates/team-members/kent-beck/TEAM-MEMBER.md"
materialized: "2026-06-08"
tier: 3
blueprint: ".config/team/team-members/kent-beck.md"
blueprint-hash: "<sha256>"
```

**(b) Materialized scripts** — a sentinel-delimited header comment block
between the shebang and the docstring, so `/dream-team:update` can replace it
in place:

```python
#!/usr/bin/env python3
# --- dream-team:provenance ---
# factory: dream-team
# factory-version: 0.5.0
# generated-by: team-update
# source: templates/team-assemble/scripts/discover-roster.py
# materialized: 2026-06-08
# tier: 2-materialized
# --- end provenance ---
"""Original module docstring continues here."""
```

**(c) Config files** (`.config/team/root.md`, blueprints) — config is
human-authored, so it carries **only** a `schema-version` line, not the full
stamp (a `factory`/`materialized` stamp would be a lie — the user owns the
file, the plugin owns the schema). See below.

**Opt-out:** an artifact carrying `provenance: detached` is an intentional
fork. `/dream-team:update` reports it but never regenerates or overwrites it.

## Config schema versioning

`.config/team/root.md` and blueprints carry a `schema-version`:

- `root.md` — a `schema-version:` line in `## Configuration`.
- team-member blueprints — a `schema-version:` line in the frontmatter.
- team blueprints — same.
- **Absent `schema-version` means version 1** (every existing repo is valid).

The plugin declares the schema version it supports in `.claude-plugin/
plugin.json` as `dreamTeamSchemaVersion`. Migration steps live in
`skills/team-member-recruit/references/schema-migrations.md`, one H2 per
version step (`## 1 → 2`), each an ordered, **idempotent, forward-only** list
of edits.

**Additive vs breaking.** A new *optional* field or section is **additive** —
an old blueprint still generates a valid skill — and does **not** bump
`schema-version`. Only a **breaking or restructuring** change (a section
renamed, a vocabulary table reshaped) bumps it and requires a migration step.
Most plugin evolution stays migration-free.

`dreamTeamSchemaVersion` is the plugin-manifest key; `schema-version` is the
per-file key inside `root.md` and blueprints — they are deliberately distinct
names.

## Lifecycle: update and migration

When the factory plugin updates, a repo's materialized artifacts may fall
behind. `/dream-team:update` (Tier 1, plugin-only) brings a repo current:

1. Discovers materialized artifacts by **provenance-stamp scan**.
2. Compares each artifact's versions against the installed plugin.
3. Classifies each: `current`, `stale`, `hand-edited`, `orphan`, `ahead`.
4. Regenerates stale artifacts, re-materializes stale scripts (atomically with
   their skill), runs config schema migrations — reporting a plan first.

Hand-edited artifacts are **never silently overwritten**: `/dream-team:update`
surfaces them for explicit per-file confirmation with a diff.

Per-member intellectual drift — "Kent wrote a new book, I want the team-member
to know about it" — is a separate flow: `team-member-update` (invoked via
natural language) re-researches a member and merges new material additively
into the blueprint, then re-materializes. This is *intellectual* drift, not
*file* drift; `/dream-team:update` handles only the latter.

## Multi-IDE materialization

Materialized artifacts must work in Claude Code, Cursor, and Codex. Every
Tier 2-materialized and Tier 3 artifact is emitted in all three forms into the
consuming repo — `.claude/`, `.cursor/`, and `.github/prompts/` — so no
contributor's tool is left without it.

## Per-feature checklist (for new features)

Every new skill, command, or feature PR must satisfy:

1. **Tier declared.** The feature's `SKILL.md` frontmatter carries a valid
   `tier:` value, justified by the team-member-vs-consultation criterion —
   and the feature passes the scope gate (it operates on team-members, teams,
   or consultations at all).
2. **No plugin leak.** If materialized, the artifact contains no
   `${CLAUDE_PLUGIN_ROOT}` and no `plugins/` path.
3. **Scripts travel with their skill.** If a materialized feature needs a
   script, the script materializes into `.claude/skills/{name}/scripts/` with
   a provenance header, referenced repo-relative.
4. **Schema discipline.** If the feature changes the shape of `root.md` or
   blueprints: additive change → no version bump; breaking change → bump
   `schema-version` and add a `schema-migrations.md` step.
5. **Provenance.** Generated and materialized artifacts carry the full
   provenance stamp.
6. **Multi-IDE.** Materialized artifacts emit Claude / Cursor / Codex forms.

## Current Feature Classification

The audit of every current feature against the criteria above. This table is
living — add a row when a feature is added.

Tier values are the frontmatter `tier:` enum: `1-plugin`, `2-plugin`,
`2-materialized`, `3`. **All `2-materialized` artifacts ship as templates
under `plugins/dream-team/templates/`** — they are not plugin-resident at
runtime. A consuming repo runs `/dream-team:recruit` (first-time) or
`/dream-team:update` to install them as repo-local artifacts under `.claude/`,
after which they work with no plugin installed. The factory's runnable
surface is only the Tier-1 commands: `/dream-team:recruit`,
`/dream-team:update`, `/dream-team:roster`.

| Feature | Operates on | Tier | Where in the plugin |
|---------|-------------|------|---------------------|
| `team-member-recruit` | team-members | `1-plugin` | `skills/team-member-recruit/` — the generator. Researches an expert (or surveys candidates for a domain), produces a blueprint, materializes the per-member skill. Absorbs the legacy `avatar-create` and `avatar-recruit` flows. |
| `team-member-add` | team-members | `1-plugin` | `skills/team-member-add/` — copies a factory-shipped team-member template into the consumer (no research). |
| `team-member-update` | team-members | `1-plugin` | `skills/team-member-update/` — re-researches an existing member to incorporate new material (book, talk, deeper coverage), merges additively into the blueprint, re-materializes. |
| `team-member-remove` | team-members | `1-plugin` | `skills/team-member-remove/` — uninstalls a member: deletes blueprint, deletes materialized skill, updates roster, prompts to remove team if member was the last. |
| `team-update` | team-members + teams | `1-plugin` | `skills/team-update/` — the lifecycle command (scan, classify, materialize, regenerate, run schema migrations). Handles file drift, not intellectual drift. |
| `team-roster` | team-members + teams | `1-plugin` | `skills/team-roster/` — status report: factory-available / locally-installed / stale / orphaned / schema-mismatched. |
| `team-assemble` | consultations | `2-materialized` | `templates/team-assemble/` — the workflow engine. Discovers roster, matches members to the request, proposes the team, selects a conversation pattern, launches teammates. Ships with the 10 conversation patterns + router + primitives in its own `patterns/` subdirectory. |
| orchestrator agent | consultations | `2-materialized` | `templates/orchestrator/` — the team lead agent. Coordinates teammates via SendMessage, executes patterns, monitors for mid-conversation signals, synthesizes findings. |
| `/consult`, `/coach`, `/plan`, `/review` entry commands | consultations | `2-materialized` | `templates/team-commands/{consult,coach,plan,review}/` — thin entries with pattern-hint frontmatter; each invokes `team-assemble` with a subroute. |
| per-team-member generated skills | consultations | `3` | Generated into the consuming repo at `.claude/skills/<slug>/` from a user-authored blueprint at `.config/team/team-members/<slug>.md`. Carries persona context + extended persona knowledge. |
| per-team generated skills | consultations | `3` | Generated into the consuming repo at `.claude/skills/team-<domain>/` from a team blueprint at `.config/team/teams/<domain>.md`. Holds shared domain knowledge that team-member skills `<extends>` into. |
| `hooks/` (PreToolUse) | team-members, teams | `1-plugin` | `hooks/` — must register with the plugin runtime; the self-sufficiency escape hatch applies. Blocks Edit/Write on files carrying `generated-by: team-member-recruit` (or any `dream-team` generator) and redirects to the blueprint + `/dream-team:update`. A no-plugin repo loses these guards (accepted trade-off, below). |
| materialized pre-commit hook | team-members, teams | `1-plugin` + `2-materialized` (dual-tier) | `scripts/team_member_validator.py` is the shared guard library. The PreToolUse hook imports it (Tier 1); `/dream-team:update --githooks` *also* materializes it (plus `check-blueprint-staged.py`) into `<repo>/.githooks/` (Tier 2) and wires a one-line invocation into the repo's `.githooks/pre-commit`. Covers the direct-shell-edit path the PreToolUse hook can't see. Requires the consumer to set `core.hooksPath` once; `/dream-team:update` offers to set it. |
| multi-IDE materialization | consultations | `1-plugin` (orchestration) + per-target output is plain on-disk content owned by the consumer | The materializer renders each artifact directly into all three IDE harness trees in a single pass: Claude (`.claude/`), Cursor (`.cursor/`), Copilot (`.github/`, with `<verb>.prompt.md` extension for entry commands). Format transforms live in `scripts/target_emit.py` (Python stdlib, no `npx` shellout). The Claude form is canonical and carries the full provenance stamp; Cursor and Copilot mirrors keep only `name` + `description` frontmatter to satisfy their schemas — provenance and drift detection track the Claude form. The agent layer is Claude-only (Cursor / Copilot have no agents concept). Targets are selectable via `materialize.py --targets`; default is all three. |
| `team-member-publish` (legacy `avatar-publish`) | factory contribution | **removed** | Stub that was never built. Removed in Phase 1 alongside the vocabulary rename. |
| `consult` skill (legacy) | consultations | **removed** | Duplicated the four entry commands' workflow step-for-step. Folded into the materialized `team-assemble` template in Phase 2c. |

## Accepted trade-offs

- **Frozen-but-functional repos.** A repo with no plugin installed keeps
  consulting its team off its materialized artifacts but cannot add or update
  members from the factory catalog. If the sole plugin-owner leaves, the repo
  freezes at its current version — the `factory-version` stamp, committed to
  git, tells a future contributor exactly what to reinstall.
- **Downgrade.** Migrations are forward-only. An older plugin must *tolerate*
  an unknown-higher `schema-version` — warn and proceed — rather than crash.
  `/dream-team:update` refuses to "downgrade-regenerate" an `ahead` artifact.
- **Hooks are plugin-only.** A no-plugin repo loses the PreToolUse blueprint
  guards. Blueprint integrity is still enforced *eventually* by
  `/dream-team:update` and the materialized pre-commit hook (run on-demand by
  the consumer), but write-time blocking only happens when the plugin is
  installed. The frozen-but-functional contract is preserved: the materialized
  consultation workflow still runs; only the runtime guards relax.
- **Node.js + `npx` is an optional dependency of `/dream-team:update`.** The
  deterministic cross-IDE fanout invokes `npx -y rulesync generate`. The
  PreToolUse hook, the pre-commit, the materialized skills themselves, and
  every other materialized artifact stay zero-dep. Without Node, the update
  flow falls back to AI-driven per-target generation using the format spec
  in `skills/team-update/references/target-formats.md`. The fallback outputs
  are functionally equivalent but may drift from rulesync's emitted format
  until Node becomes available — re-running `/dream-team:update` then
  restores rulesync output (the source of format truth) atomically.

## What CI enforces — and what it cannot

`scripts/check-factory-contract.py` mechanically verifies: every skill
declares a valid `tier:`; no materialized-tier artifact or template contains
`${CLAUDE_PLUGIN_ROOT}` or a `plugins/` path; every materialized-script
template has a parseable provenance header; `plugin.json` declares a
`dreamTeamSchemaVersion` matched by the highest version step in
`schema-migrations.md`.

CI **cannot** verify, and these stay human-reviewed: whether a tier
classification is *correct* (the team-member-vs-consultation call can be a
judgment for features that touch both); whether a feature genuinely belongs
in the plugin (the scope gate); whether a materialized skill's prose
secretly assumes the plugin; whether a migration step is truly idempotent;
whether the persona content captured in a blueprint genuinely reflects the
expert (vs hallucinated material); whether a *consuming* repo's materialized
copies are current (CI runs in the plugin repo, not consumer repos).
