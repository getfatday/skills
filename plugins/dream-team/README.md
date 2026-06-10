# dream-team

A **factory plugin** that materializes self-sufficient consultation workflows
into your repository. Recruit AI experts modeled on real-world thought
leaders, materialize them as committed repo-local files, and consult /
coach / plan / review with the team — even after you uninstall the plugin.

## What it does

The plugin's runnable surface is small: three slash commands
(`/dream-team:recruit`, `/dream-team:update`, `/dream-team:roster`) plus six
factory skills that drive the lifecycle. Everything the team needs at
*run-time* — persona skills, the team-assemble workflow engine, the
orchestrator agent, the four entry commands — lives in your repository as
plain on-disk files the materializer writes during recruitment or update.

```
your-project/
  .config/team/
    root.md                            roster manifest + schema version
    team-members/kent-beck.md          blueprint (editable source of truth)
    teams/engineering.md               team blueprint
  .claude/
    skills/kent-beck/SKILL.md          materialized persona + references
    skills/team-engineering/SKILL.md   shared domain knowledge
    skills/team-assemble/SKILL.md      workflow engine + 10 patterns
    agents/orchestrator.md             team lead
    commands/{consult,coach,plan,review}.md
  .cursor/skills/...                   Cursor mirrors (Phase 5)
  .github/skills/..., prompts/...      Copilot mirrors (Phase 5)
  .githooks/pre-commit                 blueprint-integrity hook (optional)
```

After your first invocation, the plugin can be uninstalled and the team
keeps working from the committed materialized files. That's the
self-sufficiency contract.

## Commands

| Command | Routes to | Purpose |
|---------|-----------|---------|
| `/dream-team:recruit <name-or-domain>` | `team-member-recruit` | Research a specific expert OR survey candidates for a domain. Auto-bootstraps the full catalog on first run. |
| `/dream-team:update [slug]` | `team-update` or `team-member-update` | Bulk file-drift sync, or per-slug research-driven enrichment when the blueprint is current. |
| `/dream-team:roster` | `team-roster` | Read-only status report: which members are installed, which are drifted, which need attention. |

Natural-language phrasings invoke the same skills without going through the
slash command:

- "add Marty Cagan to my team" → `team-member-add`
- "remove Kent Beck" → `team-member-remove`
- "update Kent Beck with his new book *Tidy First*" → `team-member-update`

## Bundled factory catalog

23 experts across engineering, product, design, growth, leadership, and AI
domains plus two pre-defined teams (engineering, product). The catalog is
in `marketplace.json`; first-run bootstrap installs the lot so `/consult`,
`/coach`, `/plan`, `/review` work immediately.

## Two drift modes, two cures

| Drift mode | What it means | Fix |
|------------|---------------|-----|
| **File drift** | Blueprint hand-edited, factory templates updated, mirror missing, schema bumped | `/dream-team:update` (bulk) or `/dream-team:update <slug>` |
| **Intellectual drift** | Member needs to incorporate new published material (book, talk, deeper coverage of a topic) | `team-member-update <slug>` (natural language: "update <slug> with <new material>") |

`/dream-team:roster` reports both; the slash command's router dispatches
to the right skill based on the slug's classification.

## Multi-IDE materialization

The materializer emits Claude (`.claude/`), Cursor (`.cursor/`), and Copilot
(`.github/skills/...`, `.github/prompts/<verb>.prompt.md`) variants in a
single pass. No `npx rulesync` shellout — the transforms are pure Python
stdlib. Pick a subset with `materialize.py --targets claude,cursor`.

The Claude form is canonical and carries the full provenance stamp. Cursor
and Copilot mirrors are trimmed to `name`/`description` because their
schemas reject extra fields. The PreToolUse and pre-commit hooks pivot to
the Claude sibling's stamp when guarding a mirror edit.

## Blueprint-integrity hooks

Two hooks share one validator library:

- **PreToolUse** (plugin-resident, `hooks/hooks.json`) blocks Edit/Write
  tool calls on materialized files and redirects to the blueprint plus the
  right lifecycle command.
- **Pre-commit** (materialized via `materialize.py --githooks`) catches
  the direct-shell-edit path (`vim foo.md && git commit`) so the integrity
  contract survives plugin uninstallation. Two steps to enable:
  ```
  ls .githooks/pre-commit .githooks/lib/team_member_validator.py   # confirms materialize
  git config core.hooksPath .githooks                              # wires the hook
  ```

Both honor `provenance: detached` as the documented user opt-out — once
set, the user owns the file and the hooks leave it alone.

## How the consultation runs

`/consult "what's TDD?"` triggers the materialized entry command, which
invokes the team-assemble workflow engine. The engine:

1. Reads the roster from `.config/team/root.md`.
2. Matches the request topic against each member's `domains[]` +
   vocabulary signal.
3. Proposes a team (typically 2–5 members) and picks a conversation pattern
   (debate, map-reduce, hierarchical, etc. — 10 patterns total).
4. Launches the orchestrator agent which coordinates the teammates via
   SendMessage, executes the chosen pattern, and synthesizes findings.

The teammate agents are progressive-disclosure skills: the persona context
(principles, voice, anti-patterns, vocabulary) is the system prompt; deep
references (`principles.md`, `anti-patterns.md`, `vocabulary.md`) load on
demand when topics trigger them.

## Concepts

- **Blueprint** — the editable Markdown source of truth for a member or
  team, at `.config/team/team-members/<slug>.md` or
  `.config/team/teams/<domain>.md`. Edit this; everything else is derived.
- **Materialized artifact** — what the materializer writes from a blueprint:
  the persona skill, references, mirrors. Don't edit directly; the hooks
  block it.
- **Provenance stamp** — frontmatter on every materialized file that names
  the factory, version, blueprint, blueprint-hash, and `materialized:` date.
  This is what `/dream-team:roster` reads to detect drift.
- **Factory catalog** — `marketplace.json` in the plugin lists every
  shippable member + team. First-run bootstrap installs all of them.
- **Tier** — every materialized artifact carries `tier: 1-plugin`,
  `2-materialized`, or `3` (per-member/per-team). The factory contract
  (`FACTORY.md`) explains the boundary.

## Migrating from v0.3.x

The v0.3.x plugin shipped bundled avatars, commands, agents, and patterns
all plugin-resident — uninstalling the plugin took the team with it. v1.0
moves everything except the three factory commands into your repo, where
it stays.

If you've been running v0.3.x, see [MIGRATION.md](MIGRATION.md) for the
upgrade walk-through.

## Development

The factory contract is in [FACTORY.md](FACTORY.md); the test layers and
plugin-specific rules are in [CLAUDE.md](CLAUDE.md). Run the suite with
`make test` from the repo root.
