---
name: team-member-add
tier: 1-plugin
description: "Install a team-member from the factory library into the local team. Invoked via natural language ('add Kent Beck to my team') when the user wants to re-install a catalog member without re-research. For NEW members not in the catalog, use /dream-team:recruit instead."
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
targets: ["*"]
---

# Team Member Add

Install a single team-member from the bundled factory catalog
(`${CLAUDE_PLUGIN_ROOT}/marketplace.json`) into the consumer repo. This
skill triggers on natural-language phrases like:

- "add Kent Beck to my team"
- "install Marty Cagan"
- "I want Gene Kim on the roster"

The skill is the **add-back** path — used when the catalog has the expert
the user wants. For experts NOT in the catalog (custom personas, research
required), route the user to `/dream-team:recruit "<name>"` instead.

## Step 1: Parse the request

Extract the expert name from `$ARGUMENTS`. Generate `slug` by lowercasing
and hyphenating (`"Kent Beck"` → `"kent-beck"`).

## Step 2: Catalog lookup

Read `${CLAUDE_PLUGIN_ROOT}/marketplace.json`. Find the entry where
`members[].name == "team-member-<slug>"` OR
`members[].expert == "<extracted-name>"`.

**If not in catalog:**

> "{name} isn't in the bundled dream-team catalog. To add a custom
> team-member, run `/dream-team:recruit \"{name}\"` — it'll research them
> and build a blueprint from scratch."

End the skill.

**If in catalog:** capture the canonical slug from the catalog entry
(may differ from the user's hyphenation).

## Step 3: First-run check

If `.config/team/root.md` doesn't exist, this consumer repo has never
been bootstrapped. Route the user to `/dream-team:recruit` instead — that
command's first-run flow installs the entire catalog including the
requested member in one step:

> "Your repo hasn't been bootstrapped yet. Running
> `/dream-team:recruit \"{name}\"` will install the full bundled catalog
> (including {name}) plus do the recruit. Want me to do that?"

If user agrees, invoke `/dream-team:recruit "{name}"` and return.

## Step 4: Already-installed check

If `.config/team/team-members/<slug>.md` exists, the member is already
on the roster. Read the existing blueprint, report the member's
`description:`, and end:

> "{Display Name} is already on your team. Use natural language to
> consult them (e.g. `/consult \"...\"`), or run `team-member-remove`
> first if you want to re-install fresh."

## Step 5: Install

Shell out to the materializer:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --member <slug>
```

This writes the blueprint plus the materialized persona to every IDE
harness in one shot (Phase 5 — `materialize.py` defaults to all three):

- `.config/team/team-members/<slug>.md` (blueprint, copied from factory template)
- `.claude/skills/<slug>/SKILL.md` + `references/*.md` (Claude — canonical, full provenance stamp)
- `.cursor/skills/<slug>/SKILL.md` + `references/*.md` (Cursor — frontmatter trimmed to name/description)
- `.github/skills/<slug>/SKILL.md` + `references/*.md` (Copilot — same trim, description YAML-folded)

To install for just one harness, pass `--targets claude` (or
`--targets cursor,copilot`, etc.) to `materialize.py`.

## Step 6: Team coverage

The materialized persona skill may `<extends>` a team skill (e.g. Kent
Beck extends `team-engineering`). Check whether the referenced team is
installed at `.claude/skills/team-<domain>/SKILL.md`.

**If the team is not installed:** read the member's catalog entry for
their primary domain, then check `${CLAUDE_PLUGIN_ROOT}/marketplace.json`
for a `teams[]` entry whose `members[]` includes this slug. If found,
install it too:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" \
    -C "$(git rev-parse --show-toplevel)" --team <team-slug>
```

This keeps `<extends>` resolvable in the consumer's materialized tree.

## Step 7: Update the roster manifest

Read `.config/team/root.md`. Append a row to the `## Roster` table:

| Slug | Display | Source | Enabled | Domains |
|------|---------|--------|---------|---------|
| {slug} | {Expert Name} | factory | yes | {domain1, domain2} |

Source is `factory` — this is a re-install from the bundled catalog.

If a team was added in Step 6 and the team isn't already in the
`## Teams` table, append a row there too:

| Slug | Members |
|------|---------|
| team-{domain} | {comma-separated member slugs from catalog} |

## Step 8: Confirm

Output a summary:

> Added **{Display Name}** ({slug}):
> - Domains: {list}
> - Now available in `/consult`, `/coach`, `/plan`, `/review`.
> - {Optional: team-{domain} skill (re-)installed.}

## Completion gates

- Slug exists in the factory catalog.
- Member is materialized into `.claude/skills/<slug>/`.
- Roster manifest has the new row.
- Any required team skill is installed for `<extends>` resolution.
