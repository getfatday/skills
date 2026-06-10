---
name: team-update
tier: 1-plugin
description: "Bulk sync the materialized dream-team artifacts in this repo with the installed plugin — re-materialize stale members, pull factory template updates, run schema migrations. Handles file drift, not intellectual drift (use team-member-update for that)."
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
targets: ["*"]
---

# Team Update

Bulk drift sync. Compares the materialized artifacts against the installed
plugin and resolves each drift mode declaratively. Read-only for file
content of `current` and `detached` artifacts; rewrites the rest under user
confirmation.

This skill handles **file drift** (blueprint hash drift, factory-version
drift, schema migrations, orphan cleanup). It does NOT do
**intellectual drift** — re-researching an expert because they wrote a new
book lives in Phase 4's `team-member-update`.

## Step 1: Scan

Shell out to the scanner:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py" \
    -C "$(git rev-parse --show-toplevel)"
```

Parse the JSON. Inspect the `counts` field to short-circuit when nothing
needs doing:

> If counts == {"current": N}: "Everything's in order — N artifacts, all
> current." End.

## Step 2: Build the action plan

Group `artifacts` by classification. For each non-current group, plan the
action:

| Classification | Action |
|----------------|--------|
| `current` | skip |
| `detached` | skip (user opted out) |
| `untracked` | report only (don't touch hand-written files) |
| `stale` (factory-version drift) | re-materialize via materialize.py --member \<slug\> |
| `stale` (blueprint-hash drift) | re-materialize via materialize.py --member \<slug\>; the user-edited blueprint is the new source of truth |
| `orphan` | offer to remove the materialized files (uninstall path); cleanup runs via Bash rm + roster edit |
| `ahead` | refuse to downgrade; instruct the user to install the newer plugin |
| `malformed` | offer to re-materialize (will overwrite the broken stamp) |
| `migration-needed` | run the schema-migration step from `references/schema-migrations.md` |

Build a list of (path, classification, action, slug) tuples.

## Step 3: Present the plan to the user

Use `AskUserQuestion` to confirm the plan before any writes:

```
"Update plan:
- Re-materialize {N} stale members ({slug1, slug2, ...})
- Run schema migration v{X} → v{Y}
- Refuse to touch {N} 'ahead' artifacts (downgrade not supported)
- Skip {N} 'untracked' / 'detached' files
Proceed?"
```

Options:
- "Proceed (Recommended)"
- "Show details" — print the full plan with per-file reasons, then re-ask
- "Cancel"

## Step 4: Execute

For each action in the plan:

### Re-materialize stale members or teams

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --member <slug>
```

The materializer is idempotent — re-running overwrites with the current
provenance stamp. For team artifacts, use `--team <slug>` instead.

### Re-materialize stale workflow (team-assemble, orchestrator, commands)

These don't have a per-slug flag. Run `--bootstrap` to refresh them in
place:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --bootstrap
```

### Orphan cleanup

For each orphan artifact, confirm removal (the user's blueprint is missing
but the materialized files lingered):

```bash
rm -rf .claude/skills/<slug>/ .cursor/skills/<slug>/ .github/skills/<slug>/
```

Update `.config/team/root.md` to remove the corresponding row.

### Schema migrations

If migration-needed:

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/team-member-recruit/references/schema-migrations.md`
2. For each step from `recorded` version + 1 to `target` version, apply the
   listed edits.
3. Update the `schema-version:` field in each affected config file.

If `schema-migrations.md` doesn't exist yet (Phase 2e didn't create one
because we're still on schema-version 1), `migration-needed` is impossible.

### Optional: install the materialized pre-commit hook

When the user runs `team-update` for the first time in a repo, offer to
install the materialized blueprint-integrity hook so direct shell edits
get caught at commit time (the PreToolUse hook only covers Edit/Write
inside Claude Code itself, not `vim` + `git commit`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --githooks
git config core.hooksPath .githooks
```

The hook ships its validator library alongside it under `.githooks/lib/`,
so it keeps working after the plugin is uninstalled. Bypass remains
available via `git commit --no-verify`. Skip this step if `.githooks/` is
already populated (idempotent) or the user opted out.

## Step 5: Re-scan and confirm

Run `upgrade-scan.py` again to verify all targets are now `current`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py" \
    -C "$(git rev-parse --show-toplevel)"
```

Report:

> Updated {N} artifacts:
> - {M} re-materialized
> - {O} orphans cleaned up
> - {S} schema migrations applied
> - {U} untracked/detached files left alone
>
> All {total} dream-team artifacts now current.

## Completion gates

- Scan succeeded.
- Plan presented and user confirmed (or cancelled).
- Each action executed without raising (materializer or rm errors abort).
- Final scan shows no stale/orphan/migration-needed entries.

## What this skill does NOT do

- **Add NEW catalog members.** That's `team-member-add` (natural language)
  or `/dream-team:recruit` for first-run / custom members.
- **Re-research existing members** to incorporate new books/talks. That's
  `team-member-update` (research-driven enrichment). Natural-language
  phrasings like "update Kent Beck with his new book Tidy First" trigger
  it directly. The `/dream-team:update {slug}` slash command routes here
  for `stale`/`orphan` classifications and to `team-member-update` for
  `current` ones.
- **Modify hand-written files in `.claude/`** that lack a factory stamp.
  Those are reported as `untracked`; user owns them.
