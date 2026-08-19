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
| `scripts/compile-dashboard.py` | Compiles a DASHBOARD.md status projection from your repo's own ledger and journal fragments; every source is optional (graceful when missing) |
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
| PreToolUse (`Edit\|Write\|NotebookEdit\|Bash`) | Write-once guard: Edit/NotebookEdit under the raw directory is always denied; Write there is denied only when the target already exists (creation stays legal, including shell heredoc creation). Journal fragments get the same shape; the base journal file is fully frozen (new entries are fragments). The Bash branch is a mistake-net, not a security boundary: it denies plain destructive commands aimed at an existing raw file or fragment (`rm`, `mv`, `cp` onto, `git rm`, truncating `>`/`>\|` redirection, `sed -i`/`perl -i`, `tee` without `-a`) while creation onto new paths, `tee -a`, reads, and `git checkout -- <path>` recovery stay silent. |
| UserPromptSubmit | Capture-intent nudge: on phrases like "note this" / "save that" / "write this down", adds one line of context pointing at the intake process. Precision-first with trap guards; silent otherwise. |
| SessionStart (`startup\|resume\|clear\|compact`) | Prints the standing rules pointer and byte-compares the installed CLAUDE.md block, deny rules, and GOVERNANCE.md against the plugin's canonical templates; reports any drift. Also warns when uncommitted files sit under the raw or journal-fragment directories (an uncommitted capture is one Bash command from unrecoverable — commit now), and prints a stale-dashboard line when `compile-dashboard.py --check` reports drift before the auto-refresh. |
| Stop | Minimal backstop: if the session created raw/notes files and no journal fragment exists (derived from `git status --porcelain`), block the stop once with instructions; always allows the second stop. |
| SessionStart + Stop (dashboard) | Refreshes `DASHBOARD.md` at the repo root — open decisions from your ledger, recent activity from journal fragments. A compiled projection, never authored; silent, never blocking; missing sources render as notes, not errors. |

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
| `ledger_file` | `ledger/ledger.jsonl` (optional; read only by the dashboard compiler) |

## Journal convention

One write-once fragment file per entry — `<journal_dir>/<id>-<slug>.md` with frontmatter
`id:` (monotonic integer at land time) and `date:`; no author names in the text, because git
blame on the fragment file is attribution. `scripts/compile-journal.py` renders the compiled
view deterministically, prepending a pre-existing base journal file verbatim if your repo has
one. The compiled file is a build artifact: regenerate it, never edit it.

## Identity and attribution (multi-user)

The unique id of every capture is the pair (capture-commit sha, git author email): the intake
skill ends each capture with one commit containing exactly that capture's files, and the raw
header's `captured-by:` field is filled mechanically from `git config user.email`. Two optional
committed maps make identities legible: a git-native `.mailmap` (alias emails to a canonical
one) and a `contributors.json` at the repo root keyed by canonical email:

```json
{ "<canonical email>": { "name": "<display name>", "aka": ["<alt email>", "..."] } }
```

Display names live only in this map. The dashboard resolves the current identity at render
time (`git config user.email`, canonicalized through both maps) into an `acting as` line, and
ledger decision rows may carry one optional `"assignee": "<canonical email>"` key — assigned
rows render under YOURS for that identity, everyone else sees them with the resolved display
name, and rows without an assignee render in the shared bucket for every identity (absence of
routing fails toward visibility). A row's creator is derived from `git blame` on the ledger
line, never stored; when a line is not yet committed the creator is simply omitted rather than
rendered as a placeholder, so no transient value can be committed. Both maps are optional: the
plugin renders fully without them.

### Where the name rule binds, and where it does not

The rule is scoped, because verbatim capture and name-freedom would otherwise contradict each
other:

| Surface | Rule |
|---|---|
| Raw bodies (`<raw dir>/`) | **Exempt — verbatim by design.** Dictation that names its own speaker lands untouched; the name is part of the record, and identity still resolves mechanically through `captured-by` + the landing commit. Raw files are write-once, so nothing can be scrubbed later anyway. |
| Third parties *spoken about*, in any surface | Pseudonymized at capture (`[P2]`, `[P3]`, ...) |
| Derived artifacts you author — notes, studies, the index, journal fragments | No display names. You write these, so nothing forces a name into them: use the canonical email, or drop the reference. |
| Commit subjects and bodies | No display names. Reference people by canonical email, or not at all — the author field already carries identity, and commit prose cannot be rewritten once pushed. |
| `DASHBOARD.md` | Display names appear only where this compiler *renders* them from the maps (the `acting as` line, an assignee). That is a mechanical lookup regenerated every session, not authored prose — it cannot drift or misattribute. Nothing else in the file names a person. |

The distinction is authorship, not the file. A name you type into a derived artifact or a commit
message gives a cold reader nothing git does not already give better. A name inside a verbatim
raw body is data. A name the compiler resolves out of `contributors.json` at render time is that
map doing its job — which is why you must never copy one out of the map by hand.

Note that git records identity without authenticating it, so the anchor is attribution with a
stated trust level, not proof. Where your repo has a remote: push early, protect the default
branch against force-push and deletion, and consider commit signing — server-side history is
the real durability and attribution layer. The plugin renders and guards fully with no remote
at all.

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

- 0.1.4 — identity scoping and dashboard determinism: the name rule is now scoped by *authorship* rather than applied blanket-wide. Raw bodies are verbatim by design — dictation that names its own speaker lands untouched, because the name is part of the record and identity already resolves through `captured-by` plus the landing commit (0.1.3 left this collision unresolved, so the flow had to guess). The never-prose rule binds every surface the flow *authors*: distilled notes, the index line, journal fragments, and — new — commit subjects and bodies, which reference people by canonical email or not at all, since commit prose cannot be rewritten once pushed and a display name never has to be looked up out of `contributors.json` to write one. `DASHBOARD.md` is committed by the flow rather than left untracked, and `compile-dashboard.py` no longer emits render-time-only values into it: a ledger row whose line has no landing commit yet renders with no creator segment instead of a `(uncommitted)` placeholder, so a committed dashboard cannot freeze a state that has already moved on. The CLAUDE-block gains the capture-commit step it was missing and the scoping rules, so a session that commits without invoking the skill is still guided. README stays the changelog home.
- 0.1.3 — multi-user identity and durability: the capture id is the (capture-commit sha, git author email) pair — the intake skill gains a per-capture COMMIT step, the raw header gains a mechanical `captured-by:` field and returns `source:` to external provenance only (third-party names pseudonymized; the author is git-resolved, never prose); the dashboard gains an `acting as` who-am-I line (canonicalized through optional `.mailmap` + `contributors.json`), an optional per-row `assignee` key with YOURS / others / shared buckets, and blame-derived row creators; the write-once guard gains a Bash mistake-net branch denying plain destructive commands against existing raw files and fragments (creation, `tee -a`, reads, and `git checkout` recovery stay silent); SessionStart warns on uncommitted capture files and consumes `compile-dashboard.py --check` for a stale-dashboard line; `templates/dashboard-features.json` records the portable feature set for drift measurement. README stays the changelog home.
- 0.1.2 — ships the portable status dashboard: `scripts/compile-dashboard.py` compiles `DASHBOARD.md` from your repo's own ledger and journal fragments (open decisions + recent activity; graceful when either source is missing), refreshed by SessionStart and Stop hook lines. README stays the changelog home — the plugin manifest carries no changelog key.
- 0.1.1 — the intake skill and the CLAUDE-block capture rule name the sanctioned `tee`-heredoc creation path for new write-once files (raw files, journal fragments); settings deny unchanged.
