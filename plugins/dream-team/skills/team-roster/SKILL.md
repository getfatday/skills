---
name: team-roster
tier: 1-plugin
description: "Report status of every materialized dream-team artifact in this repo — current, stale, hand-edited, orphaned, ahead, or schema-mismatched. Read-only; doesn't change anything."
user-invocable: true
allowed-tools: [Read, Bash, Glob, Grep]
targets: ["*"]
---

# Team Roster

Read-only status report. Tells the user what's installed, what's drifted,
and what needs attention. Doesn't touch any files. To resolve drift, point
the user at `/dream-team:update`.

## Step 1: Scan the repo

Shell out to the scanner:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade-scan.py" \
    -C "$(git rev-parse --show-toplevel)"
```

Parse the JSON output. The structure is:

```json
{
  "installed": {
    "factory-version": "0.5.2",
    "generator-version": "0.1",
    "dream-team-schema-version": 1
  },
  "counts": {"current": 10, "stale": 1, ...},
  "artifacts": [
    {"path": ".claude/skills/kent-beck/SKILL.md", "kind": "skill",
     "classification": "current", "reasons": [], "provenance": {...}},
    ...
  ]
}
```

## Step 2: Detect uninstalled state

If `artifacts` is empty (the scan walked the repo and found nothing
materialized), the dream-team hasn't been installed in this repo:

> "No materialized dream-team artifacts found. Run `/dream-team:recruit
> <name>` to bootstrap the bundled catalog."

End.

## Step 3: Summarize installed members

Group `artifacts` by classification. For each member (kind `config-member`),
look up the corresponding materialized skill at `.claude/skills/<slug>/`
to determine factory vs local source (read the persona skill's
`generated-by:` — `team-member-recruit` with a `templates/` source = factory;
otherwise = local).

Present the summary:

> **Dream team status**
>
> Plugin: dream-team v{factory-version}
>
> **Installed members ({count}):**
> | Slug | Display | Source | Status |
> |------|---------|--------|--------|
> | kent-beck | Kent Beck | factory | current |
> | our-cto | Our CTO | local | current |
> | marty-cagan | Marty Cagan | factory | **stale** (factory-version drift) |
> | ... | ... | ... | ... |
>
> **Teams ({count}):**
> | Slug | Members |
> |------|---------|
> | team-engineering | kent-beck, robert-martin, eric-evans, ... |
>
> **Workflow ({count} files):** {all current / 1 stale: orchestrator.md / ...}

For Display name, read the blueprint's `name:` frontmatter or the materialized
skill's persona section.

## Step 4: Highlight needs-attention items

If any artifact has a classification other than `current`:

> **Needs attention:**
> - **stale ({count})** — re-materialize via `/dream-team:update`
>   - `.claude/skills/marty-cagan/SKILL.md` (factory-version 0.5.0 → 0.5.2)
>   - `.config/team/team-members/kent-beck.md` was edited; materialized skill is now stale
> - **orphan ({count})** — blueprint deleted; either remove the materialized
>   files (run `team-member-remove`) or restore the blueprint
> - **hand-edited / untracked ({count})** — files in .claude/skills/ without
>   provenance stamps; could be user-created or from a different factory
> - **ahead ({count})** — recorded factory-version is NEWER than installed;
>   plugin was downgraded — install the newer dream-team plugin to upgrade
> - **migration-needed ({count})** — config schema is older than the
>   plugin's supported version; `/dream-team:update` runs migrations

For each classification group with count > 0, list at most 5 paths inline;
say "+{N} more" if there are more.

## Step 5: Recommend next step

Based on the summary:

- All current: "Everything's in order."
- Any stale or migration-needed: "Run `/dream-team:update` to bring the
  workflow + members current with the installed plugin."
- Any orphan: "Run `team-member-remove <slug>` for each orphan, or restore
  the blueprint and re-run `/dream-team:update`."
- Any ahead: "The installed plugin (v{installed}) is OLDER than what
  materialized these files. Install dream-team v{recorded} or newer."
- Any untracked/detached: "These look hand-written or opted out of
  factory management. Left alone."

## Completion gates

- Scan completed and JSON parsed.
- Summary presented covering members, teams, workflow.
- Drift items listed by classification with paths.
- Next-step recommendation matches the observed state.
