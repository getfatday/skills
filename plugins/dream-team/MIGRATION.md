# Migrating from v0.3.x to v1.0

The v0.3.x plugin shipped 23 bundled avatars, four entry commands, the
orchestrator agent, and the workflow engine all as plugin-resident files.
Uninstalling the plugin removed the team with it.

v1.0 reshapes dream-team as a **factory**: the plugin ships only the
compile-time machinery (the recruit / update / roster commands and their
six driving skills); your repository holds every run-time artifact. The
result is self-sufficiency — once your team is materialized, the plugin
is optional.

## What changes for you

| Concern | v0.3.x | v1.0 |
|---------|--------|------|
| Where bundled avatars live | `plugins/dream-team/avatars/<slug>/` | Your repo: `.config/team/team-members/<slug>.md` (blueprint) + `.claude/skills/<slug>/SKILL.md` (materialized) |
| Where the `/consult`, `/coach`, `/plan`, `/review` commands live | Plugin-resident | Your repo: `.claude/commands/<verb>.md` |
| Where the workflow engine and orchestrator live | Plugin: `skills/assemble/`, `agents/orchestrator.md`, `patterns/` | Your repo: `.claude/skills/team-assemble/`, `.claude/agents/orchestrator.md` |
| How you add a new member | `/dream-team:create` (plugin-resident skill) | `/dream-team:recruit <name>` or natural language ("add Marty Cagan") |
| How you keep the team current | Re-install plugin | `/dream-team:update` (file drift) or "update X with Y" (intellectual drift) |
| Schema vocabulary | `avatar` everywhere (`AVATAR.md`, `avatars/`) | `team-member` everywhere (`TEAM-MEMBER.md`, `templates/team-members/`) |
| Out-of-the-box IDE support | Claude only | Claude + Cursor + Copilot in a single materialize pass |

## Before you upgrade

**Back up any custom v0.3 avatars.** If you authored avatars beyond the
bundled 21, copy the contents of `.claude/skills/<avatar>/` somewhere
safe — v1.0 cannot auto-translate v0.3 `AVATAR.md` into v1.0 blueprints
(the schemas differ), and after the migration the old files surface as
`untracked` rather than as runnable persona skills. You'll use the
backup as research material when re-running `/dream-team:recruit`.

**Check your `.gitignore`.** Step 3 stages `.config/team/`, `.claude/`,
`.cursor/`, `.github/`. If you intentionally ignore `.cursor/` or
`.github/skills/`, either drop the entry or run the bootstrap with
`--targets claude` (see step 2) to limit emission to the IDE you commit.

## The migration in three steps

### 1. Update the plugin to v1.0

Per Claude Code's normal plugin update flow. If you installed from the
marketplace:

```
/plugin update dream-team
```

Verify with:

```
/dream-team:roster
```

A fresh-from-v0.3 repo will report every existing `.claude/skills/<avatar>/`
file as **`untracked`** — the v0.3 files predate the v1.0 provenance
stamp, so the scanner can't tell them apart from any other hand-written
skill. That's expected; step 2 overwrites them with properly-stamped
v1.0 artifacts. Members you authored yourself (not from the v0.3 bundled
catalog) need the back-up from "Before you upgrade" above — step 2 won't
preserve them.

### 2. Bootstrap the full catalog

Run `/dream-team:recruit` once. The first invocation auto-bootstraps:

- Materializes the workflow engine into `.claude/skills/team-assemble/`
  (SKILL.md + the ten conversation patterns + the router).
- Materializes the orchestrator agent into `.claude/agents/orchestrator.md`.
- Materializes the four entry commands (`.claude/commands/consult.md` etc.).
- Materializes every bundled member's blueprint and persona skill
  (`.config/team/team-members/<slug>.md` + `.claude/skills/<slug>/SKILL.md`).
- Materializes every bundled team (`.config/team/teams/engineering.md` +
  `.claude/skills/team-engineering/SKILL.md`).
- Mirrors all of the above into `.cursor/` and `.github/`.
- Writes the roster manifest at `.config/team/root.md`.

Use any phrasing — `/dream-team:recruit "Our CTO"` (a new member) or
`/dream-team:recruit "devops"` (a domain survey). The bootstrap fires
once before the recruit logic runs. Subsequent calls skip the bootstrap
(idempotent — `root.md`'s existence is the sentinel).

After this finishes, `/consult`, `/coach`, `/plan`, `/review` work
immediately. Everything you had in v0.3 is now in your repo.

### 3. Commit the materialized artifacts

```
git add .config/team .claude .cursor .github
git commit -m "dream-team v1.0 bootstrap"
```

That's it. The plugin can be uninstalled from this point and the team
keeps working off the committed files.

## Optional: install the blueprint-integrity hook

Phase 6 ships a PreToolUse hook plugin-side that blocks accidental edits
to materialized files inside Claude Code. To extend the same guard to
direct shell edits, materialize the pre-commit hook:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" -C "$(git rev-parse --show-toplevel)" --githooks
git config core.hooksPath .githooks
```

The hook ships its validator library colocated under `.githooks/lib/`, so
it survives plugin uninstallation. Bypass is the standard
`git commit --no-verify` (named in the block message so contributors
don't have to guess).

## Optional: drop unused catalog members

The bootstrap installs all 23 members. To prune:

```
"remove Andy Grove from my team"
"remove Nir Eyal from my team"
```

These trigger `team-member-remove`, which uninstalls the blueprint + all
three IDE-harness skill directories and updates the roster manifest.

## Optional: add a custom member

If your team has a CTO, principal, or any expert the catalog doesn't ship:

```
/dream-team:recruit "Our CTO"
```

This invokes Mode A of `team-member-recruit`: the WebSearch-driven
research engine extracts the six dimensions (principles, mental models,
vocabulary, anti-patterns, cycle, voice), writes a blueprint, and
materializes the persona skill. Custom members are stamped
`source: local` in the roster manifest so you can tell them apart from
factory-sourced rows at a glance. `/dream-team:update` re-materializes
from each blueprint (factory and local alike), so your hand-written
content survives the update — that's the whole point of the blueprint
being the editable source of truth.

## Vocabulary cheat-sheet

| v0.3.x | v1.0 |
|--------|------|
| avatar | team-member |
| `AVATAR.md` (per-avatar) | `TEAM-MEMBER.md` (template) + `<slug>.md` (blueprint) |
| `avatars/<slug>/` | `templates/team-members/<slug>/` (plugin) + `.config/team/team-members/` (consumer) |
| `schema/AVATAR.md` | `skills/team-member-recruit/references/team-member-blueprint-schema.md` |
| `avatar-create` skill | `team-member-recruit` (research-driven) + `team-member-add` (mechanical) |
| `avatar-publish` | (removed) |
| `/dream-team:create` | `/dream-team:recruit` (auto-bootstraps + research) or `team-member-add` natural-language |
| `/consult`, `/coach`, `/plan`, `/review` (plugin-resident) | Same commands, now materialized into `.claude/commands/<verb>.md` — work after plugin uninstall |
| `agents/orchestrator.md` (plugin) | `.claude/agents/orchestrator.md` (materialized) |
| `patterns/` (plugin) | `.claude/skills/team-assemble/patterns/` (materialized) |

## Where to read more

- [README.md](README.md) — what dream-team is and how it works
- [FACTORY.md](FACTORY.md) — the factory contract (tiers, self-sufficiency,
  provenance stamp, schema versioning)
- [CLAUDE.md](CLAUDE.md) — test layers, xfail conventions, layout rules
  (for contributors)

## Troubleshooting

**`/dream-team:roster` shows `mirror-missing` after a fresh bootstrap.**
Your bootstrap defaulted to a subset of IDE harnesses (e.g., you set
`--targets claude`). Re-run `materialize.py --all --targets claude,cursor,copilot`
or just `/dream-team:update` (which defaults to all three).

**An edit gets blocked by the PreToolUse hook and you really need to edit
a materialized file.** Two paths: (a) the supported way — edit the
blueprint at `.config/team/team-members/<slug>.md` and run
`/dream-team:update <slug>` to re-materialize; or (b) the opt-out — add
`provenance: detached` to the file's frontmatter. The validator honors
this and the file is yours from then on.

**Custom v0.3 avatars not in the v1.0 catalog.** The migration above
only restores bundled catalog members. Custom avatars from v0.3 need to
be re-researched via `/dream-team:recruit "<expert name>"` because the
v0.3 schema differs from v1.0's. Migration of arbitrary v0.3 `AVATAR.md`
files into v1.0 blueprints is not automated.

**The materialized files keep regenerating with the wrong content.** You
edited the materialized file rather than the blueprint. The materializer
treats `.config/team/team-members/<slug>.md` as the source of truth. Move
your edits there and the next `/dream-team:update` (or
`materialize.py --member <slug> --keep-blueprint`) will respect them.
