---
name: avatar-create
description: "Create a new avatar agent — research an expert, analyze their work, generate avatar plugin + domain team plugin"
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
---

# Avatar Creation Pipeline

You are a skill that creates avatar plugins from real-world experts. You work in three stages: COLLECT, ANALYZE, BUILD. Each stage has a completion gate that must pass before advancing.

Parse the expert name from `$ARGUMENTS` (e.g., "Kent Beck"). Generate `expert-slug` by lowercasing and hyphenating (e.g., "kent-beck").

## Batch Mode

If `$ARGUMENTS` contains `--batch`, skip all intermediate AskUserQuestion checkpoints (source review, analysis review, build confirmation). The user has already confirmed they want this avatar. Run the full pipeline end-to-end without stopping.

Batch mode still:
- Performs all research and analysis (no shortcuts on quality)
- Presents the final reconciliation summary in the completion output
- Stops on errors (missing sources, analysis gaps)

Batch mode does NOT:
- Ask "are there sources I missed?"
- Ask "does this capture the expert accurately?"
- Ask "does this avatar look correct?"

When invoked from `/avatar-recruit`, batch mode is always on.

## Naming Conventions

These are non-negotiable. Every avatar follows this pattern:

- **Plugin dir**: `plugins/avatar-{first-last}/` (full name, never abbreviated)
- **Command prefix**: `{first-last}` in plugin.json (e.g., `/kent-beck:consult`)
- **Skill dir**: `skills/{first-last}/` (person-namespaced, NOT domain-namespaced)
- **Domain tags**: in AVATAR.md `domains[]` for orchestrator routing only

Never use domain names as command prefixes or skill directory names. Two experts in the same domain must not collide.

---

## Stage 1: COLLECT — Gather Source Material

### Setup

Create working directory at `.avatar-workspace/{expert-slug}/research/`.

### Research

Use WebSearch to find the expert's:
- **Bibliography**: books, major publications
- **Talks/keynotes**: conference presentations, recorded lectures
- **Blog posts**: personal blog, guest posts, notable articles
- **Podcasts**: appearances as guest or host
- **Named frameworks/methodologies**: models they created or popularized

### Document

For each source found, create a research note at `.avatar-workspace/{expert-slug}/research/{source-slug}.md` using the template at `../../templates/research-note.md`. Fill in every section — leave none blank. Quote directly when possible.

### Catalog

Build a source catalog at `.avatar-workspace/{expert-slug}/research/sources.md` listing all research notes with:
- Source title
- Source type (book, blog, talk, podcast, interview, paper)
- URL if available
- Key contribution (one line)

### User Checkpoint

**If NOT batch mode:** Use AskUserQuestion to present the source catalog. Ask:
- "Are there sources I missed that you'd like me to add?"
- "Should I proceed with analysis?"
Let the user add more sources. Create research notes for any additions.

**If batch mode:** Log the source count and proceed.

### Completion Gate

- At least 3 sources cataloged
- User confirmed to proceed (or batch mode)

---

## Stage 2: ANALYZE — Deep Extraction

### Read All Research

Read every research note from `.avatar-workspace/{expert-slug}/research/`.

### Cross-Reference and Extract

Analyze across all sources to identify patterns. Extract these six dimensions:

1. **Principles** — Beliefs appearing in multiple sources. Strongest signal = most repeated across sources. Each principle needs source citations.

2. **Mental Models** — Named frameworks they return to repeatedly. Note frequency across sources and when each model applies.

3. **Vocabulary** — Terms they coined or use with specific meaning. Deduplicate across sources. Note where each term first appeared.

4. **Anti-Patterns** — Things they explicitly warn against. This is the most distinctive content — it defines what the expert would refuse to do. Include examples and corrections.

5. **Process/Cycle** — The sequence or methodology they prescribe. Map it as a repeating cycle: Step 1 → Step 2 → ... → Step N → (back to Step 1).

6. **Voice** — How they frame problems, use metaphors, argue positions. Capture:
   - Framing style (how they introduce problems)
   - Metaphor patterns (recurring analogies)
   - Argument structure (how they build a case)
   - Distinctive phrases (verbal tics, catchphrases)

### Write Analysis

Write the complete analysis to `.avatar-workspace/{expert-slug}/analysis.md` using the template at `../../templates/analysis.md`. Every section must have source citations pointing back to specific research notes.

### User Checkpoint

**If NOT batch mode:** Use AskUserQuestion to present the analysis summary. Show:
- Number of principles extracted
- Key mental models identified
- Anti-pattern count
- Cycle model overview
Ask: "Does this capture the expert accurately? Anything to add or correct?"

**If batch mode:** Log the analysis dimensions and proceed.

### Completion Gate

- All 6 sections populated with source citations
- User approved the analysis (or batch mode)

---

## Stage 3: BUILD — Generate the Avatar Plugin

### Step 3a: Configuration

**If NOT batch mode:** Use AskUserQuestion to ask the user for:
- **Domain name**: The primary domain this avatar covers (e.g., "engineering", "product")
- **Confirm mapping**: "Does {expert-name} → {domain} look right?"
- **Additional domains[]**: Any secondary domain tags

**If batch mode:** Infer the primary domain and secondary domains from the analysis Domain Mapping table. Use the area with the highest depth rating as the primary domain.

### Step 3b: Check for Domain Intersections

For each domain in the new avatar's `domains[]`, check if any existing avatar (in `plugins/avatar-*/AVATAR.md`) already claims that domain.

- **No intersections**: this avatar is the sole expert in all its domains. Go to Step 3c.
- **Intersections found**: another avatar shares one or more domains. Go to Step 3d.

### Step 3c: No Intersection — Avatar Only

The avatar owns all its concepts. No domain team needed.

**Generate avatar plugin** at `plugins/avatar-{expert-slug}/`:

```
plugins/avatar-{expert-slug}/
  AVATAR.md              # Identity, domains[], all principles, voice, anti-patterns
  CLAUDE.md              # Voice rules, vocabulary enforcement
  plugin.json            # commandPrefix: {expert-slug}
  agents/
    orchestrator.md      # Intent routing
    challenger.md        # Anti-pattern reviewer
  commands/
    consult.md           # /{expert-slug}:consult
    coach.md             # /{expert-slug}:coach
    review.md            # /{expert-slug}:review
    plan.md              # /{expert-slug}:plan
  skills/
    {expert-slug}/
      SKILL.md           # All expertise (self-contained)
      references/
        principles.md    # All principles < 3K tokens
        anti-patterns.md # All warnings < 3K tokens
        vocabulary.md    # All terms < 3K tokens
```

The avatar is fully self-contained. Everything lives in the avatar plugin.

### Step 3d: Intersection Found — Create Domain Team + Reconcile

Two or more avatars share a domain. A domain team is needed to hold shared concepts.

**For each intersecting domain** (not all domains, only the ones that overlap):

1. **Check if `plugins/team-{domain}/` exists:**
   - If NOT: create it now (first intersection triggers team creation)
   - If YES: update it (add new member, reconcile new concepts)

2. **Read both avatars' content** for the intersecting domain

3. **Classify concepts into shared vs unique:**
   - **Shared**: concepts BOTH avatars agree on (same vocabulary term, same principle). Move to `team-{domain}`.
   - **Unique**: concepts only ONE avatar holds, or where they disagree. Stay in the avatar.

4. **Uniqueness constraint**: a vocabulary term, principle, or anti-pattern can exist in at most ONE team plugin. If "refactor" fits both `team-engineering` and `team-tdd`, pick the most specific domain. Present ambiguous cases to the user via AskUserQuestion.

5. **Update existing avatar plugins**: remove concepts that moved to the team. Add an `<extends>` reference to the team skill.

6. **Generate/update team plugin:**

```
plugins/team-{domain}/
  TEAM.md                # Domain identity, members[], shared domains
  skills/
    {domain}/
      SKILL.md           # Shared concepts for the domain
      references/
        vocabulary.md    # Canonical definitions (owned by this team only)
        principles.md    # Principles all members agree on
```

**TEAM.md schema:**
```yaml
---
name: "{Domain Name}"
description: "Shared {domain} knowledge across avatar members"
domains:
  - "{domain}"
members:
  - "avatar-{first-member}"
  - "avatar-{second-member}"
---
```

7. **Present reconciliation to user** via AskUserQuestion before applying changes. Show what moves where. **In batch mode:** log the reconciliation summary and proceed.

**Key rule: teams are only created on intersection, never for a solo avatar.** The first avatar in a domain is self-contained. Teams emerge when a second avatar proves shared concepts exist.

### Step 3e: Content Rules

- **AVATAR.md** must match the schema at `../../schema/AVATAR.md`
- **SKILL.md** must be under 2K tokens
- **Reference files** must each be under 3K tokens
- **plugin.json** `commandPrefix` = the expert slug (NOT the domain)
- All content must trace back to the analysis. Never invent content.
- All internal references use person-namespaced paths: `skills/{expert-slug}/`
- A concept (vocabulary term, principle, anti-pattern) can exist in at most ONE location across all plugins

### Step 3f: Update Marketplace

Update `plugins/dream-team/marketplace.json` — add to the `avatars` array:

```json
{
  "name": "avatar-{expert-slug}",
  "expert": "{Expert Name}",
  "domains": ["{domain1}", "{domain2}"],
  "path": "plugins/avatar-{expert-slug}"
}
```

If domain teams were created or updated, add/update the `teams` array:

```json
{
  "name": "team-{domain}",
  "domain": "{domain}",
  "members": ["avatar-{first}", "avatar-{second}"],
  "path": "plugins/team-{domain}"
}
```

### Step 3g: Final Checkpoint

**If NOT batch mode:** Use AskUserQuestion to present:
- List of all generated files
- AVATAR.md preview (principles + voice)
- If teams created: reconciliation summary (what moved where)
Ask: "Does this look correct? Ready to finalize?"

**If batch mode:** Output a summary line: "Created avatar-{slug}: {N} files, domains: [{domains}], teams: [{teams created/updated}]"

### Completion Gate

- Avatar plugin generated with person-namespaced structure
- Domain teams created only if intersections exist, reconciled if they do
- No concept duplicated across plugins
- marketplace.json updated
- User confirmed (or batch mode)
