---
name: avatar-create
description: "Create a new avatar agent — research an expert, analyze their work, generate a complete avatar plugin"
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
---

# Avatar Creation Pipeline

You are a skill that creates avatar plugins from real-world experts. You work in three stages: COLLECT, ANALYZE, BUILD. Each stage has a completion gate that must pass before advancing.

Parse the expert name from `$ARGUMENTS` (e.g., "Kent Beck"). Generate `expert-slug` by lowercasing and hyphenating (e.g., "kent-beck").

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

Use AskUserQuestion to present the source catalog. Ask:
- "Are there sources I missed that you'd like me to add?"
- "Should I proceed with analysis?"

Let the user add more sources. Create research notes for any additions.

### Completion Gate

- At least 3 sources cataloged
- User confirmed to proceed

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

Use AskUserQuestion to present the analysis summary. Show:
- Number of principles extracted
- Key mental models identified
- Anti-pattern count
- Cycle model overview

Ask: "Does this capture the expert accurately? Anything to add or correct?"

### Completion Gate

- All 6 sections populated with source citations
- User approved the analysis

---

## Stage 3: BUILD — Generate the Avatar Plugin

### Configuration

Use AskUserQuestion to ask the user for:
- **Domain name**: The primary domain this avatar covers (e.g., "engineering", "product", "testing")
- **Confirm mapping**: "Does {expert-name} → {domain} look right?"
- **Additional domains[]**: Any secondary domain tags

### Generate Plugin

Generate the complete avatar plugin at `plugins/avatar-{expert-slug}/` using templates from `../../templates/avatar-plugin/`. Every template placeholder must be filled from the analysis — never invent content.

#### File Structure

```
plugins/avatar-{expert-slug}/
  AVATAR.md              # From ../../templates/avatar-plugin/AVATAR.md
  CLAUDE.md              # From ../../templates/avatar-plugin/CLAUDE.md
  plugin.json            # From ../../templates/avatar-plugin/plugin.json
  agents/
    orchestrator.md      # From ../../templates/avatar-plugin/orchestrator.md
    challenger.md        # From ../../templates/avatar-plugin/challenger.md
  commands/
    consult.md           # From ../../templates/avatar-plugin/consult.md
    coach.md             # From ../../templates/avatar-plugin/coach.md
    review.md            # From ../../templates/avatar-plugin/review.md
    plan.md              # From ../../templates/avatar-plugin/plan.md
  skills/
    {domain}/
      SKILL.md           # From ../../templates/avatar-plugin/SKILL.md
      references/
        principles.md    # Extended principles with citations < 3K tokens
        anti-patterns.md # Extended anti-patterns < 3K tokens
        vocabulary.md    # Full vocabulary table < 3K tokens
```

#### Content Rules

- **AVATAR.md** must match the schema at `../../schema/AVATAR.md`
- **SKILL.md** must be under 2K tokens — keep it tight
- **Reference files** must each be under 3K tokens
- **plugin.json** `commandPrefix` = the primary domain name
- All content must trace back to the analysis. If it is not in the analysis, it does not go in the plugin.

#### Reference Files

These are NOT templated — generate them directly from the analysis:

- `references/principles.md` — Full principle descriptions with source citations, examples, and when-to-apply guidance
- `references/anti-patterns.md` — Full anti-pattern descriptions with detection signals, examples, and corrections
- `references/vocabulary.md` — Complete vocabulary table with definitions, usage examples, and common misuses

### Update Marketplace

After generating the plugin, update `plugins/dream-team/marketplace.json` by adding an entry to the `avatars` array:

```json
{
  "name": "avatar-{expert-slug}",
  "expert": "{Expert Name}",
  "domains": ["{domain1}", "{domain2}"],
  "path": "plugins/avatar-{expert-slug}"
}
```

### Final Checkpoint

Use AskUserQuestion to present:
- List of all generated files
- AVATAR.md preview (principles + voice)
- Plugin.json contents

Ask: "Does this avatar look correct? Ready to finalize?"

### Completion Gate

- All files generated and match templates
- marketplace.json updated
- User confirmed
