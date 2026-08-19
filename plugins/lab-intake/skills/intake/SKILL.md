---
name: intake
description: Ingest any new knowledge into this repository through its capture process (adapted from the ingest flow in Karpathy's LLM Wiki pattern) — findings, learnings, notes, decisions, or files Claude creates for its own reference. Use this skill whenever you are about to save, write down, record, capture, or file away information that is not an edit to existing content — even if the user just says "note this", "save that", "remember this", or you are creating a self-reference file. Every new knowledge artifact enters through this process.
---

# Capture knowledge into the repository

This repository runs on a capture convention adapted from the ingest flow in Karpathy's LLM Wiki
pattern (which contributes the linked-wiki, index, and append-only log ideas but is explicitly
abstract and optional): every piece of knowledge lives in exactly one right place, is as small as
it can be, is linked so it can be found, and is journaled so its arrival is traceable. Unfiled or
duplicated knowledge silently rots — nothing bypasses this process, including files you create
for your own reference.

## Paths

Defaults below; if `.claude/lab-intake.json` exists at the repo root, its values override
them. Run `/lab-intake:init` once per repository to scaffold everything.

| Purpose | Default |
|---|---|
| Raw verbatim sources (write-once) | `research/raw/` |
| Distilled pages / studies | the directory holding the index file (default `research/`) |
| Self-reference notes | `research/notes/` |
| Wiki index (one line per page) | `research/index.md` |
| Journal fragments (write-once) | `experiments/journal-fragments/` |

## Process

0. **Raw first** — if the input is something substantial a human said or provided verbatim
   (brain dump, pasted doc, transcript, key external source), file it untouched in
   `<raw dir>/<YYYY-MM-DD>-<slug>.md` *before* distilling, opening with a provenance header.
   Create the new file with a Bash `tee` heredoc — the sanctioned creation mechanism for
   write-once files (the settings deny protects existing records; creation flows through
   `tee`):

   ```
   tee "<raw dir>/<YYYY-MM-DD>-<slug>.md" << 'EOF'
   ---
   source: <person, URL, meeting, or document this came from>
   date: <YYYY-MM-DD the material was produced or received>
   context: <one line — why this is landing in the repository>
   ---

   <the verbatim material, untouched, below the header>
   EOF
   ```

   Raw files are never edited after creation (a PreToolUse hook denies it); distillations link
   to them, and disagreements resolve in favor of raw.
1. **Classify** what you're capturing — one right home:
   - A study or an external finding → a page in the directory holding the index file
     (default `research/<topic>.md`).
   - A testable idea about a way of working — a hunch an experiment could confirm or refute →
     if the lab-loop plugin is installed (its `hypothesis` skill appears in your available
     skills), register it there as a hypothesis spec instead of filing a note; otherwise file
     it under the notes directory with the word `testable` on its first line, so it can
     graduate to a spec later.
   - Self-reference material (conventions, lookups, notes-to-future-Claude) →
     `<notes dir>/<slug>.md`.
   - A decision about how the repository works → if the repo keeps a human-edited directives
     file, never edit it: propose the change to the user and journal the proposal.
   - An observation about how work happened → usually a journal fragment alone (step 4), not a
     new page.
2. **Minimize** — write the smallest document that fully carries the knowledge. Strip anything
   speculative or generic. Rule of thumb: if the knowledge is a single sentence or directly
   extends an existing doc's scope, add it there surgically; a separate file is warranted only
   when the content is operational detail that would bloat its would-be host.
3. **Link** — every new file must be referenced from at least one existing document a reader
   would plausibly start from, and added to the index file as one line under the right section:
   `- [<title>](<relative path>) — <one-line summary>`. A file nothing points to is lost.
4. **Journal** — record the arrival as one write-once fragment
   `<journal dir>/<id>-<slug>.md`, where id = highest existing fragment id + 1. Create it via
   `tee` heredoc like raw files (the settings deny protects existing records; creation flows
   through `tee`):

   ```
   tee "<journal dir>/<id>-<slug>.md" << 'EOF'
   ---
   id: <next integer>
   date: <YYYY-MM-DD>
   type: capture
   ---

   <one short paragraph: what was captured, where it landed, and why>
   EOF
   ```

   Fragments are write-once — create the file once and never modify it (the hook denies
   edits); no author names in the text (git blame is attribution). Refresh the compiled view
   with `python3 scripts/compile-journal.py` when useful.

## Rules

- One fact, one home. If knowledge would live in two places, pick one and link from the other.
- Sources stay attached: external claims keep their URLs.
- Never edit raw files, past journal fragments, or a human-only directives file.
- If it's unclear where something belongs, say what's ambiguous and ask rather than guessing.
