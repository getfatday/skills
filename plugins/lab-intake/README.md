# lab-intake

Karpathy-style knowledge intake for any repo: write-once raw capture with provenance, distilled
linked notes, a one-line-per-page index, and an append-only journal — enforced by hooks, not
prose. `/lab-intake:init` scaffolds your repo and writes the durable guard rules; capture
triggers on "note this".

**Scope.** This is an intake discipline — append-only raw capture plus distillation — not a
typed CRUD document lifecycle. Knowledge arrives once, stays verbatim in raw, and gets
distilled, linked, indexed, and journaled. If you need managed document types with
create/update/delete workflows, use a document-management plugin instead.

## Provenance

The method is adapted from — not identical to — the ingest flow in Andrej Karpathy's LLM Wiki
pattern, which contributes the linked-wiki, index, and append-only log ideas but is explicitly
abstract and optional. The working-principle phrasing echoed in the capture rule comes via the
community karpathy-skills write-up, authored by Forrest Chang from Karpathy's observations, not
by Karpathy.

## Quick start

1. Install the plugin (from your marketplace, or load a checkout directly with
   `claude --plugin-dir <path-to>/lab-intake`).
2. In your repository, run `/lab-intake:init`. It scaffolds the directories and index,
   installs a marker-delimited rules block into `CLAUDE.md`, and writes settings deny rules —
   then commit the scaffold.
3. Say "note this: …" (or just start saving knowledge). The `intake` skill routes it:
   raw-first when verbatim, one right home, minimal, linked + indexed, journaled.

## What ships

| Component | Purpose |
|---|---|
| `skills/intake/` | The capture process: raw-first, classify, minimize, link + index, journal |
| `skills/init/` | User-invoked scaffold (idempotent; also repairs drift) |
| `hooks/hooks.json` + `hooks/scripts/` | Deterministic guards (see table below) |
| `scripts/compile-journal.py` | Renders the compiled journal view from write-once fragments (copied into your repo by init) |
| `scripts/init-scaffold.py` | The deterministic scaffold init runs |
| `templates/` | Canonical copies of everything init writes (drift is checked against these) |
| `evals/` | Eval cases for `claude plugin eval` (neutral fixtures) |

## The three layers

A plugin cannot inject project memory or permission rules into a consumer repository, so every
mechanism ships three ways:

1. **Hooks** — deterministic guards, active while the plugin is enabled.
2. **Durable repository artifacts** — written into your repo by `init` and drift-checked at
   session start: the `CLAUDE.md` rules block, `.claude/settings.json` deny rules,
   `GOVERNANCE.md`, and the compile script. These survive a plugin disable.
3. **Skill prose** — the procedure itself, in the `intake` skill.

## Hooks

| Event | Behavior |
|---|---|
| PreToolUse (`Edit\|Write\|NotebookEdit`) | Write-once guard: Edit/NotebookEdit under the raw directory is always denied; Write there is denied only when the target already exists (creation stays legal, including shell heredoc creation). Journal fragments get the same shape; the base journal file is fully frozen (new entries are fragments). |
| UserPromptSubmit | Capture-intent nudge: on phrases like "note this" / "save that" / "write this down", adds one line of context pointing at the intake process. Precision-first with trap guards; silent otherwise. |
| SessionStart (`startup\|resume\|clear\|compact`) | Prints the standing rules pointer and byte-compares the installed CLAUDE.md block, deny rules, and GOVERNANCE.md against the plugin's canonical templates; reports any drift. |
| Stop | Minimal backstop: if the session created raw/notes files and no journal fragment exists (derived from `git status --porcelain`), block the stop once with instructions; always allows the second stop. |

All hook scripts are stdlib-only Python, fail open on any error, and use consumer-generic paths.

## Configuration

`init` writes `.claude/lab-intake.json` at your repo root; hooks and the compile script
read it. All paths are repo-relative.

| Key | Default |
|---|---|
| `raw_dir` | `research/raw` |
| `notes_dir` | `research/notes` |
| `index_file` | `research/index.md` |
| `journal_dir` | `experiments/journal-fragments` |
| `journal_file` | `experiments/journal.md` (optional base; only used if your repo already has one) |
| `compiled_file` | `experiments/journal-compiled.md` |

## Journal convention

One write-once fragment file per entry — `<journal_dir>/<id>-<slug>.md` with frontmatter
`id:` (monotonic integer at land time) and `date:`; no author names in the text, because git
blame on the fragment file is attribution. `scripts/compile-journal.py` renders the compiled
view deterministically, prepending a pre-existing base journal file verbatim if your repo has
one. The compiled file is a build artifact: regenerate it, never edit it.

## Known limitations

- The capture-intent nudge covers interactive sessions; it is not verified to fire under
  headless `-p` runs. Enforcement does not depend on it.
- The Stop backstop only sees uncommitted work; a session that commits everything is trusted to
  have journaled (the compile script and reviews catch gaps).
- Index maintenance is a step of the intake skill, not an automated projection.
- In some builds, `Write()`/`NotebookEdit()` permission rules in settings are not enforced;
  the PreToolUse hook is the stronger guard, and the settings `Edit` denies are the layer that
  survives a plugin disable.
- Testable ideas: with the companion lab-loop plugin installed (hypothesis specs, fixed
  budgets, binary assertions, mechanical verdicts), the intake skill routes them there; without
  it, they are filed as notes tagged `testable` so they can graduate later.

## Evals

```
claude plugin eval . --scaffold
```

`--scaffold` is required: each case's `scaffold_script` git-inits a neutral fixture repo. The
`raw-write-once` case is the should-not-act guard test — it passes only when the hook denies an
edit to an existing raw file.

## Changelog

- 0.1.1 — the intake skill and the CLAUDE-block capture rule name the sanctioned `tee`-heredoc creation path for new write-once files (raw files, journal fragments); settings deny unchanged.
