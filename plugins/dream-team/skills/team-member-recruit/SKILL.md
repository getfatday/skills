---
name: team-member-recruit
tier: 1-plugin
generator-version: "0.1"
description: "Recruit a new team-member into the dream team — research a named expert OR survey candidates for a domain or skillset. Auto-bootstraps the full factory roster on first run."
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
targets: ["*"]
---

# Team Member Recruitment

`/dream-team:recruit [name-or-domain]` is the user-facing entry point for
**adding new team-members** that the factory catalog doesn't already ship.
The bundled catalog (23 experts in `${CLAUDE_PLUGIN_ROOT}/marketplace.json`)
auto-installs on first run, so by the time you reach the recruit flow the
dream team is already working — recruit is for hiring talent the catalog
doesn't have.

Two modes, dispatched on the shape of `$ARGUMENTS`:

- **Mode A — Specific person.** Argument names a single expert
  (`"Our CTO"`, `"Jane Smith"`, `"Geoffrey Hinton"`). Research that person
  via the [research-engine](references/research-engine.md), write the
  blueprint, emit the materialized persona skill.
- **Mode B — Domain or skillset survey.** Argument is a domain or skill
  description (`"devops"`, `"find me an SRE expert"`, `"product analytics"`).
  Survey candidates, present a scored shortlist, then run Mode A for each
  selected expert.

## Provenance stamp emitted onto materialized artifacts

Every per-team-member skill, per-team skill, agent, command, and pattern
materialized by this generator (or by `team-update`) carries a full
provenance frontmatter block. See `${CLAUDE_PLUGIN_ROOT}/FACTORY.md` for the
contract. The materializer at `${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py`
injects the stamp; the canonical shape is:

```yaml
factory: 'dream-team'
factory-version: '0.5.0'
generated-by: 'team-member-recruit'
generator-version: '0.1'
source: 'templates/team-members/kent-beck/skills/kent-beck/SKILL.md'
materialized: '2026-06-08'
tier: 3
blueprint: '.config/team/team-members/kent-beck.md'
blueprint-hash: '<sha256>'
```

Tier 3 (per-member, per-team) adds `blueprint:` and `blueprint-hash:`.
Tier 2-materialized (team-assemble, orchestrator, entry commands) omits
those two fields. `tier:` is template-owned — never overwritten by the
materializer.

---

## Step 0 — First-run bootstrap

Before any mode dispatch, check whether the consumer repo has been
bootstrapped:

```
Read .config/team/root.md
```

**If it exists:** skip to Step 1.

**If it does NOT exist:** the dream team has never been installed in this
repo. Run the bootstrap:

1. Materialize the full catalog (workflow engine + orchestrator + 4 entry
   commands + every catalog member + every team). Use Bash:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/materialize.py" -C "$(git rev-parse --show-toplevel)" --all
   ```

   This emits ~100+ files into `.config/team/` and `.claude/`. The members
   are listed in `${CLAUDE_PLUGIN_ROOT}/marketplace.json`.

2. Write `.config/team/root.md` with `schema-version: 1` and the populated
   `## Roster` table mirroring the materialized members:

   ```markdown
   ---
   schema-version: 1
   ---

   # Team Root

   ## Configuration
   - schema-version: 1

   ## Roster
   | Slug | Display | Source | Enabled | Domains |
   |------|---------|--------|---------|---------|
   | kent-beck | Kent Beck | factory | yes | engineering, tdd, software-design |
   | ... | ... | factory | yes | ... |

   ## Teams
   | Slug | Members |
   |------|---------|
   | team-engineering | kent-beck, robert-martin, eric-evans, martin-fowler, lisa-crispin |
   | team-product | marty-cagan, teresa-torres, eric-ries |
   ```

   Read `${CLAUDE_PLUGIN_ROOT}/marketplace.json` to populate the table rows
   exactly. Source is `factory` for every bootstrap row.

3. Tell the user: "Dream team bootstrapped with N members across M domains.
   `/consult`, `/coach`, `/plan`, `/review` are ready. Continuing with
   recruit for `[arg]`…"

Bootstrap is idempotent: re-running it overwrites the materialized files
in-place (the materializer carries provenance stamps so drift is detectable).
`root.md` is the sentinel — its absence triggers bootstrap, its presence
skips it.

---

## Step 1 — Mode dispatch

Parse `$ARGUMENTS`. Decide the mode:

- **Mode A signals**: capitalized multi-word string ("Our CTO", "Jane Smith"),
  presence of `--name <X>` or `--expert <X>`, or a phrasing like
  "research <name>".
- **Mode B signals**: a lowercase domain-y token ("devops", "sre",
  "product analytics"), or a phrasing like "find <X> experts" / "survey
  the <X> domain".

**If genuinely ambiguous** (the user says `"devops"` — could be the domain,
could be a hypothetical handle?), use `AskUserQuestion`:

> "Research `[arg]` as a specific expert, or survey the `[arg]` domain?"

with two options: `"Specific expert (Mode A)"` and `"Domain survey (Mode B)"`.

Once mode is decided, proceed to the matching section.

---

## Mode A — Research a specific person

Compute `expert-slug` by lowercasing and hyphenating the name
(`"Kent Beck"` → `"kent-beck"`, `"Our CTO"` → `"our-cto"`).

### A1. Run the research engine

Follow the [research-engine](references/research-engine.md) methodology:

1. **COLLECT** — gather sources via WebSearch, document each into the
   workspace at `.team-member-workspace/{expert-slug}/research/`.
2. **ANALYZE** — extract the six dimensions (principles, mental models,
   vocabulary, anti-patterns, cycle, voice) into
   `.team-member-workspace/{expert-slug}/analysis.md`.

The research engine has its own user checkpoints (source review, analysis
review). Honor them unless the caller passes `--batch` (Mode B invokes this
inline with batch mode on).

### A2. Check domain intersections

Read the existing roster blueprints at
`.config/team/team-members/*.md`. Compare the new member's `domains[]`
against each existing member's `domains[]`.

- **No intersection** — the new member owns all their concepts. Proceed
  to A3 as a solo member.
- **One or more intersections** — at least one existing member shares a
  domain. A domain team may need to be created or updated.

For each intersecting domain, check whether a team blueprint exists at
`.config/team/teams/<domain>.md`:

- **Team exists** — read it. The team blueprint already declares shared
  vocabulary/principles for the domain. Make sure the new member's content
  refers to those shared terms (don't re-declare them in the persona skill;
  let `<extends>` pick them up).
- **Team does not exist** — generating the team is a structural change that
  belongs to `team-update` (Phase 3). For now, present the intersection to
  the user via `AskUserQuestion`:
  > "[New Member] shares the `<domain>` domain with [Existing Member].
  > Should I create a `team-<domain>` shared-knowledge skill to hold the
  > common ground? (Otherwise both members will redeclare the shared terms.)"
  Default: yes.

### A3. Write the blueprint

Generate the blueprint at `.config/team/team-members/<expert-slug>.md` with
the required schema:

```markdown
---
name: "{Expert Name}"
schema-version: 1
description: "{one-line description — leads with the expert's unique topics}"
domains:
  - "{primary-domain}"
  - "{secondary-domain}"
---

# {Expert Name}

<principles>
1. **{Principle name}** — {description} ({source citation})
...
</principles>

<voice>
{Framing style, metaphor patterns, argument structure, distinctive phrases,
all grounded in the analysis.}
</voice>

<anti-patterns>
- **{Anti-pattern}** — {what to avoid and why}
...
</anti-patterns>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| ... | ... | ... |
</vocabulary>
```

The `description:` should lead with the expert's *unique* topics
(vocabulary they coined, their named frameworks) rather than shared-domain
generalities. This matters for Claude Code's progressive-disclosure
triggering — see `${CLAUDE_PLUGIN_ROOT}/FACTORY.md`.

### A4. Materialize the persona skill

Write the materialized persona skill and references directly. There is no
factory template for net-new members; the blueprint IS the source. Files:

- `.claude/skills/<expert-slug>/SKILL.md` — persona context for the
  teammate agent. Mirror the structure of any existing factory member
  (e.g. `${CLAUDE_PLUGIN_ROOT}/templates/team-members/kent-beck/skills/kent-beck/SKILL.md`).
  Use `<extends>` blocks to inherit shared domain content from any
  team-<domain> skills.
- `.claude/skills/<expert-slug>/references/principles.md` — extended
  principles (≤ 3K tokens) drawing from the analysis.
- `.claude/skills/<expert-slug>/references/anti-patterns.md` — extended
  warnings.
- `.claude/skills/<expert-slug>/references/vocabulary.md` — full vocabulary.

Each generated file carries the full provenance frontmatter shown at the
top of this skill. For research-driven members, `source:` is
`.config/team/team-members/<expert-slug>.md` (the blueprint) and
`blueprint:` / `blueprint-hash:` reference the same file.

### A5. Update the roster manifest

Read `.config/team/root.md`. Append a row to the `## Roster` table:

| Slug | Display | Source | Enabled | Domains |
|------|---------|--------|---------|---------|
| {slug} | {Expert Name} | local | yes | {domain1, domain2} |

Source is `local` (not `factory`) — this is a custom team-member, not from
the bundled catalog. If a team-<domain> was created in A2, append it to
the `## Teams` table as well.

### A6. Confirm with the user

Output a summary:

> Recruited **{Expert Name}** ({slug}):
> - Domains: {list}
> - Sources: {N}
> - {Optional: team-<domain> created/updated}
>
> Now available in `/consult`, `/coach`, `/plan`, `/review`.

---

## Mode B — Domain or skillset survey

### B1. Understand the ask

If `$ARGUMENTS` is a clean domain string (`"devops"`), use it directly. If
it's natural-language (`"find me an SRE expert"`), extract the domain.

### B2. Check existing coverage

Read `${CLAUDE_PLUGIN_ROOT}/marketplace.json` and the consumer's
`.config/team/root.md` roster. Report:

- "You have N team-members covering these domains: [list]"
- "The domain `{input}` is {covered by [X, Y] / not yet covered}"

If the domain is already covered, note which members cover it. The user
may still want additional perspectives.

### B3. Research candidates

Use `WebSearch` to find thought leaders in the requested domain. Search for:

- "{domain} thought leaders authors"
- "{domain} best books practitioners"
- "{domain} conference keynote speakers"
- "{domain} methodology framework creators"

For each candidate found, gather:

- Name
- Books: count + titles
- Blog/Newsletter: active? URL? frequency?
- Talks: YouTube/TED/conference presence?
- Named frameworks: specific models people reference by name
- Domain coverage: what specific areas within the domain

Search for at least 8–10 candidates before filtering.

### B4. Score candidates

Score each candidate 0–5 per dimension:

| Dimension | What to look for | 5 = ideal |
|-----------|-----------------|-----------|
| Books | Published works with principles, not just stories | 3+ books on the domain |
| Blog / active writing | Current thinking, not just historical | Active blog/newsletter, weekly+ |
| Talks / video | Voice, framing, argument style visible | Multiple conference talks on YouTube |
| Named frameworks | Specific models people reference by name | 3+ named frameworks widely known |
| Strong opinions | Anti-patterns, refusals, controversial positions | Known for what they reject |
| Domain intersection | Shares domains with existing team-members | Triggers team creation |

Total score: 0–30. Candidates below 15 are unlikely to produce a
high-quality team-member (not enough source material for deep extraction).

### B5. Check intersections

For each candidate, also check:
- Do they intersect with any existing roster member's domains? (Note which)
- Would adding them trigger a domain-team reconciliation?

### B6. Present candidates

Use `AskUserQuestion` with `multiSelect: true` over the top 5–7 candidates:

```
"Which experts should I research and add to the team?"

- "Charity Majors (28/30)" — Observability Engineering, complex-systems debugging. Intersects with Kim on devops.
- "Liz Fong-Jones (25/30)" — SRE practice, on-call hygiene. New angle: SRE leadership.
- "Tanya Reilly (24/30)" — Staff Engineer's Path, tech-lead growth. Intersects with Larson.
...
```

The options should be the candidate names. The user can select one or more.

### B7. Order and execute

Determine the optimal recruitment order:

1. Candidates with the most intersections go **first** — they trigger team
   reconciliation early so later candidates build on a reconciled state.
2. Candidates with partial intersection go next.
3. Candidates with no intersection go last (clean solo members).

Present the recruitment order to the user with a brief explanation.

Then for each selected candidate, run **Mode A inline** (steps A1–A6) with
batch mode implicit (the user already approved this whole list). Between
each, note:

- What domain teams were created or updated
- How the next candidate's intersection picture changed

### B8. Confirm

Summarize the cohort:

> Recruited {N} team-members: {names}
> Teams created/updated: {list}
> Now available in `/consult`, `/coach`, `/plan`, `/review`.

---

## Completion gates

- For Mode A: blueprint + materialized skill + references all written;
  roster manifest updated; user confirmed (or batch).
- For Mode B: at least 5 candidates researched and scored; user selected
  ≥ 1; all selected recruited via inline Mode A (or user explicitly
  stopped mid-list); recruitment order honored intersection dependencies.
