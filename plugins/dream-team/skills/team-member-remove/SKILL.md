---
name: team-member-remove
tier: 1-plugin
description: "Uninstall a team-member from the local team — delete the blueprint, the materialized persona skill + references, and remove the row from the roster manifest. Invoked via natural language ('remove Kent Beck', 'uninstall Marty Cagan')."
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
targets: ["*"]
---

# Team Member Remove

Uninstall a single team-member from the consumer repo. This skill
triggers on natural-language phrases like:

- "remove Kent Beck"
- "uninstall Marty Cagan"
- "drop Gene Kim from the team"

Removal is destructive — the materialized files go away. The blueprint
(`.config/team/team-members/<slug>.md`) goes away too. The user can
re-add a catalog member later via `team-member-add` or
`/dream-team:recruit`, but a custom (research-driven) member is **gone
for good** unless they re-research them.

## Step 1: Parse the request

Extract the name from `$ARGUMENTS`. Generate `slug` by lowercasing and
hyphenating.

## Step 2: Locate the member

Read `.config/team/team-members/<slug>.md`. If it doesn't exist, the
member isn't installed:

> "{name} isn't on your team — `.config/team/team-members/<slug>.md`
> doesn't exist. Nothing to remove."

End the skill.

## Step 3: Confirm with the user

Read the blueprint's `<source>` (the frontmatter has a description and
domains). Detect whether this is a factory or local member by reading
the corresponding row in `.config/team/root.md`'s `## Roster` table.

Use `AskUserQuestion` to confirm:

```
"Remove {Display Name} ({slug}) from your team?
This deletes:
- .config/team/team-members/{slug}.md (blueprint)
- .claude/skills/{slug}/ (materialized persona + references)
- The roster entry in .config/team/root.md

{If 'local' source: WARNING: This member is research-driven, not from
the factory catalog. You'll lose the research unless you've committed
the blueprint to git.}"
```

Options:
- "Remove (Recommended)"
- "Cancel"

If user picks Cancel, end the skill.

## Step 4: Delete the files

Use `Bash` for the recursive directory removal:

```bash
rm -f .config/team/team-members/<slug>.md
rm -rf .claude/skills/<slug>/ .cursor/skills/<slug>/ .github/skills/<slug>/
```

If both removals succeed, continue. If they fail, surface the error and
stop.

## Step 5: Update the roster manifest

Read `.config/team/root.md`. Find the row in `## Roster` where the
first column matches `<slug>`. Remove that row from the table.

Write the updated `root.md` back.

## Step 6: Team-orphan detection

For each team blueprint at `.config/team/teams/<team-slug>.md`, read the
frontmatter `members[]` field. If the removed member was in any team's
members list, check whether ANY of that team's remaining members are
still installed (have a blueprint at
`.config/team/team-members/<member-slug>.md`).

- **Other members still installed:** edit the team blueprint to remove
  the deleted member from `members[]`. The team stays.
- **No other members installed:** the team is now orphaned. Use
  `AskUserQuestion`:

  ```
  "Removing {removed-name} leaves team-{domain} with no installed
  members. Remove the team skill too?"
  ```

  Options:
  - "Remove team-{domain}" — deletes `.config/team/teams/<team-slug>.md`,
    `.claude/skills/team-<team-slug>/`, and the team's row in
    `.config/team/root.md`'s `## Teams` table.
  - "Keep team-{domain}" — leaves the team skill in place even though no
    member <extends> it. Useful if the user plans to re-add a member
    soon.

  Default: Remove.

## Step 7: Confirm

Output a summary:

> Removed **{Display Name}** ({slug}):
> - Deleted: blueprint + materialized skill + references
> - Roster updated
> - {Optional: team-{domain} also removed (was orphaned)}
>
> Re-add later with `team-member-add "{name}"` (if in catalog) or
> `/dream-team:recruit "{name}"` (custom).

## Completion gates

- Blueprint deleted.
- Materialized `.claude/skills/<slug>/` deleted.
- Roster manifest row removed.
- Any orphan team-skill cleanup handled (or explicitly skipped).
