# Research Engine

The methodology for turning a real-world expert into a faithful team-member
persona. Used by `team-member-recruit` (initial creation) and, in Phase 4,
by `team-member-update` (incremental enrichment when an expert publishes
new material).

The output of this methodology is an **analysis** containing six dimensions,
written to `.team-member-workspace/{expert-slug}/analysis.md`. The caller
(recruit / update) is responsible for turning the analysis into a blueprint
and materializing it.

---

## Stage 1 — COLLECT: gather source material

### Setup

Create working directory at `.team-member-workspace/{expert-slug}/research/`
(under the consumer repo, not the plugin tree).

### Research

Use WebSearch to find the expert's:

- **Bibliography**: books, major publications
- **Talks/keynotes**: conference presentations, recorded lectures
- **Blog posts**: personal blog, guest posts, notable articles
- **Podcasts**: appearances as guest or host
- **Named frameworks/methodologies**: models they created or popularized

### Document

For each source found, create a research note at
`.team-member-workspace/{expert-slug}/research/{source-slug}.md` using the
template at `${CLAUDE_PLUGIN_ROOT}/templates/research-note.md`. Fill in every
section — leave none blank. Quote directly when possible.

### Catalog

Build a source catalog at
`.team-member-workspace/{expert-slug}/research/sources.md` listing all
research notes with:

- Source title
- Source type (book, blog, talk, podcast, interview, paper)
- URL if available
- Key contribution (one line)

### User checkpoint (interactive mode)

**If NOT batch mode:** Use `AskUserQuestion` to present the source catalog:
- "Are there sources I missed that you'd like me to add?"
- "Should I proceed with analysis?"

Let the user add more sources. Create research notes for any additions.

**If batch mode:** Log the source count and proceed.

### Completion gate

- At least 3 sources cataloged
- User confirmed to proceed (or batch mode)

---

## Stage 2 — ANALYZE: deep extraction

### Read all research

Read every research note from `.team-member-workspace/{expert-slug}/research/`.

### Cross-reference and extract

Analyze across all sources to identify patterns. Extract these six dimensions:

1. **Principles** — Beliefs appearing in multiple sources. Strongest signal =
   most repeated across sources. Each principle needs source citations.

2. **Mental Models** — Named frameworks they return to repeatedly. Note
   frequency across sources and when each model applies.

3. **Vocabulary** — Terms they coined or use with specific meaning.
   Deduplicate across sources. Note where each term first appeared.

4. **Anti-Patterns** — Things they explicitly warn against. This is the most
   distinctive content — it defines what the expert would refuse to do.
   Include examples and corrections.

5. **Process/Cycle** — The sequence or methodology they prescribe. Map it as
   a repeating cycle: Step 1 → Step 2 → ... → Step N → (back to Step 1).

6. **Voice** — How they frame problems, use metaphors, argue positions.
   Capture:
   - Framing style (how they introduce problems)
   - Metaphor patterns (recurring analogies)
   - Argument structure (how they build a case)
   - Distinctive phrases (verbal tics, catchphrases)

### Write analysis

Write the complete analysis to
`.team-member-workspace/{expert-slug}/analysis.md` using the template at
`${CLAUDE_PLUGIN_ROOT}/templates/analysis.md`. Every section must have source
citations pointing back to specific research notes.

### User checkpoint (interactive mode)

**If NOT batch mode:** Use `AskUserQuestion` to present the analysis summary:
- Number of principles extracted
- Key mental models identified
- Anti-pattern count
- Cycle model overview

Ask: "Does this capture the expert accurately? Anything to add or correct?"

**If batch mode:** Log the analysis dimensions and proceed.

### Completion gate

- All 6 sections populated with source citations
- User approved the analysis (or batch mode)

---

## Incremental research (Phase 4 — `team-member-update`)

When `team-member-update` re-runs this methodology on an existing member:

- Read the existing blueprint at `.config/team/team-members/{expert-slug}.md`
  first. It already declares the member's principles, vocabulary, voice, etc.
- The user usually names specific NEW material (a new book, a new talk,
  a new podcast appearance). COLLECT targets only that new material — do
  not re-research the entire expert from scratch.
- The new analysis is **additive**: principles/vocabulary/anti-patterns
  extracted from new sources get **merged** into the existing blueprint,
  not used to overwrite it. Conflicts (same term, different meaning) are
  surfaced to the user via `AskUserQuestion` for resolution.
- Voice is the most fragile dimension. New material can sharpen or update
  vocabulary and add principles, but the existing voice characterization
  is rarely wrong — preserve it unless the new material contradicts it
  outright.

The completion gate for update is: at least one new dimension changed
(principles, vocabulary, anti-patterns, mental models, cycle), and the
existing voice characterization has not been silently overwritten.
