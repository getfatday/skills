# crux

Crux gives any repository three disciplines in one plugin, profile-gated so you adopt only
what you need:

- **Capture** (default profile): write-once raw capture with provenance, distilled linked
  notes, a one-line-per-page index, an append-only journal of write-once fragments, and a
  compiled status dashboard — enforced by hooks, not prose.
- **Experiments** (+profile): every "does X actually work?" becomes a spec with 3-5 binary
  pass/fail assertions BEFORE anything runs; fixed budgets with halt-on-breach; verdicts
  (keep/discard/refine) decided mechanically from assertions; every run journaled, including
  failures. A deterministic preflight gates runs.
- **Modeling** (+profile): the repository's way of working becomes an explicit operating
  model you can mine from evidence (`adopt`), trace sessions against (`observe`), audit
  (`evaluate`), compile into executable workflows (`compile`), execute (`run`), and
  A/B-test changes to (`verify`). Policy nodes are enforced by a generic interpreter — the
  node file is the configuration.

`/crux:init` scaffolds your repo per profile and writes the durable guard rules; capture
triggers on "note this".

**Scope.** Crux is a way-of-working discipline — append-only capture, evidence-grade
experiments, an explicit process model — not a typed CRUD document lifecycle, a task
tracker, or a CI system. If you need managed document types with create/update/delete
workflows, use a document-management plugin instead.

## Provenance

The capture method is adapted from — not identical to — the ingest flow in Andrej
Karpathy's LLM Wiki pattern, which contributes the linked-wiki, index, and append-only log
ideas but is explicitly abstract and optional. The experiment loop is adapted from — not
identical to — Karpathy's autoresearch (modify, train five minutes, check improvement, keep
or discard, repeat); the spec/assertion/budget/verdict machinery is this plugin's design.
The working-principle phrasing echoed in the capture rule comes via the community
karpathy-skills write-up, authored by Forrest Chang from Karpathy's observations, not by
Karpathy. The modeling grammar synthesizes an event-storming-derived node schema with the
public Event Modeling canon (see `grammar/`).

## Quick start

1. Install the plugin from your marketplace (`claude plugin install crux@<marketplace-id>`
   — the hosting marketplace's README carries the exact id), or load a checkout directly
   with `claude --plugin-dir <path-to>/crux`.
2. In your repository, run `/crux:init` (add `--profile experiments` or
   `--profile modeling` to activate more). It scaffolds the directories, installs a
   marker-delimited rules block into `CLAUDE.md`, and writes settings deny rules — then
   commit the scaffold.
3. Say "note this: ..." to capture; "test whether X actually works" to run the experiment
   loop; "model how we work here" to mine the operating model.

Upgrading from the retired predecessor plugins (the earlier standalone capture and
experiment-loop plugins): install crux and re-run `/crux:init` — it migrates the legacy
config files and CLAUDE.md rules blocks in place.

## Skills

| Skill | Profile | Purpose |
|---|---|---|
| `init` | — | Profile-gated scaffold (idempotent; repairs drift; migrates legacy installs) |
| `intake` | capture | The capture process: raw-first, classify, minimize, link + index, journal, commit |
| `hypothesis` | experiments | The experiment loop: spec, preflight, budgeted run, binary evaluation, mechanical verdict, journal |
| `adopt` | modeling | Mine the repo + recorded sessions into a SCHEMA-shaped operating model |
| `observe` | modeling | Trace a recorded session against the model: node-tagged, token-attributed, citation-validated |
| `evaluate` | modeling | Audit the model for defects with evidence pointers and zero fabrications |
| `compile` | modeling | Regenerate executable artifacts (workflows, runners, skills, rule blocks) deterministically from model nodes |
| `run` | modeling | Execute a compiled flow to a mechanical verdict (adopt-first refusal routing) |
| `verify` | modeling | Controlled A/B experiments over way-of-working interventions |

## What ships

| Component | Purpose |
|---|---|
| `skills/` | The nine skills above |
| `hooks/hooks.json` + `hooks/scripts/` | Deterministic guards (see table below) |
| `scripts/compile-journal.py` | Renders the compiled journal view from write-once fragments (copied into your repo by init) |
| `scripts/compile-dashboard.py` | Compiles a DASHBOARD.md status projection from your repo's own ledger and journal fragments; every source is optional |
| `scripts/init-scaffold.py` | The deterministic profile-gated scaffold init runs |
| `scripts/preflight.py` | The deterministic spec preflight (copied into your repo by init at the experiments profile) |
| `scripts/compile-model-workflow.py` | The model-to-executable compiler: one flow in, a dynamic-workflow target + a portable runner + a shared GWT assertion manifest out |
| `scripts/model-to-board.py`, `scripts/render_flow.py`, `scripts/flow_composer.py` | The diagram lane: model nodes to a board serialization to rendered flow views |
| `scripts/em-slice-lint.py` | Mechanical conformance lint over the board serialization (rules EM-L1..EM-L10) |
| `scripts/lexicon-lint.py` | Glossary conformance lint over model text (advisory) |
| `scripts/currency-lint.py` | Stale-value lint: current-state claims in node bodies verified against the cited artifacts (ADVISORY, non-certifying) |
| `scripts/doctor-classify.py` | Environment-health doctor, detection half: types the OAuth credential surface (CLEAN / FLAP-DEGRADED / HARD-EXPIRED / INDETERMINATE) from recorded probe streams or a live read-only snapshot — see `docs/doctor.md` |
| `scripts/doctor-remediate.py` | Environment-health doctor, remediation half: the frozen four-state ladder — exactly one next step per typed state, fail-closed heal verification |
| `scripts/review-cadence.py` | The verdict-forcing review cadence: ranked REVIEW DEBT surface + append-only verdict appender (multi-evidence) — see `docs/review-cadence.md` |
| `scripts/waste-status.py` | Advisory flow instrument: idle-runnable, terminal-pickup, and void-meter waste metrics from committed timestamps alone (exit 0 always, never a gate) |
| `scripts/parity-check.py` | Byte-parity checker between an installed crux copy and a published manifest or pinned reference tree (see “Install parity” below) |
| `kernel/operating-model/SCHEMA.md` | The node grammar (+ `SCHEMA-DELTA.md`, this copy's deltas) |
| `kernel/harness/` | The frozen extraction protocol, grading rubric, and trace-citation validator |
| `grammar/` | The Event Modeling layer: metamodel, slice-board layout + lint rules, schema-to-EM mapping |
| `docs/workflow-format-reference.md` | The dynamic-workflow emission format the compiler targets |
| `templates/` | Canonical copies of everything init writes (drift is checked against these) |
| `evals/` | One eval suite per skill, `claude plugin eval` format (neutral fixtures) |

## The three layers

A plugin cannot inject project memory or permission rules into a consumer repository, so
every mechanism ships three ways:

1. **Hooks** — deterministic guards, active while the plugin is enabled.
2. **Durable repository artifacts** — written into your repo by `init` and drift-checked at
   session start: the `CLAUDE.md` rules block, `.claude/settings.json` deny rules,
   `GOVERNANCE.md`, and the installed scripts. These survive a plugin disable.
3. **Skill prose** — the procedures themselves.

## Hooks

| Event | Behavior |
|---|---|
| PreToolUse (`Edit\|Write\|NotebookEdit\|Bash`) | Write-once guard: Edit/NotebookEdit under the raw directory is always denied; Write there is denied only when the target already exists (creation stays legal, including shell heredoc creation). Journal fragments get the same shape; the base journal file is fully frozen. The Bash branch is a mistake-net denying plain destructive commands aimed at an existing raw file or fragment. |
| PreToolUse (same matcher) | Generic policy interpreter: reads `operating-model/*/policies/*.md` as data. `enforcement: hook` nodes with a `mechanism:` block deny; `enforcement: advisory` nodes print one advisory line and never affect the exit code. No model, no effect. |
| PreToolUse (`Bash`, run-shaped) | Preflight gate (experiments profile): headless agent invocations tied to an experiment are denied when the spec is missing or fails the shipped preflight. |
| PreToolUse (`Bash`, `git commit`) | Advisory backstop (experiments profile): a tinker-shaped commit with no hypothesis spec staged prints a one-line nudge. Never blocks. |
| UserPromptSubmit | Capture-intent nudge on phrases like "note this" / "save that". Precision-first; silent otherwise. |
| SessionStart | Standing rules pointer + drift check against the plugin's canonical templates; uncommitted-capture warning; stale-dashboard check and refresh. |
| Stop | Unjournaled-work backstop (blocks once with instructions when new knowledge files have no journal fragment); dashboard refresh. |

All hook scripts are stdlib-only Python, fail open on any error, and use consumer-generic
paths.

## Configuration

`init` writes `.claude/crux.json` at your repo root; hooks, skills, and the compile scripts
read it. All paths are repo-relative.

| Key | Default |
|---|---|
| `profile` | `capture` (`experiments` and `modeling` add layers) |
| `raw_dir` | `research/raw` |
| `notes_dir` | `research/notes` |
| `index_file` | `research/index.md` |
| `journal_dir` | `experiments/journal-fragments` |
| `journal_file` | `experiments/journal.md` (optional base; only used if your repo already has one) |
| `compiled_file` | `experiments/journal-compiled.md` |
| `hypotheses_dir` | `hypotheses` |
| `runs_dir` | `experiments/runs` |
| `template_file` | `hypotheses/TEMPLATE.md` |
| `preflight_file` | `experiments/preflight.py` |
| `model_dir` | `operating-model` |
| `context` | the repository directory name (slugified) |

## Install parity

Drift between an installed crux copy and its published referent is measured, never assumed.
`scripts/parity-check.py --install <dir> (--manifest <published-manifest> | --reference <tree>)`
prints one finding per diverged/missing/extra file with its shipped file class and exits
nonzero; silent exit 0 is parity. Repair direction matters: a drifted INSTALL is restored
from the published referent; when the SOURCE moved ahead, the repair is a new versioned
publish — never an in-place overwrite of a published version. The checker is the counted
instrument of the parity law (hypothesis H-181 in the source lab, kept 2026-08-26: a clean
install grades zero findings, every seeded divergence is detected with path and class, and
the sync procedure restores byte parity without touching counted history).

## Journal convention

One write-once fragment file per entry — `<journal_dir>/<id>-<slug>.md` with frontmatter
`id:` (monotonic integer at land time) and `date:`; no author names in the text, because
git blame on the fragment file is attribution. `scripts/compile-journal.py` renders the
compiled view deterministically, prepending a pre-existing base journal file verbatim if
your repo has one. The compiled file is a build artifact: regenerate it, never edit it.

## Identity and attribution (multi-user)

The unique id of every capture is the pair (capture-commit sha, git author email). Two
optional committed maps make identities legible: a git-native `.mailmap` and a
`contributors.json` at the repo root keyed by canonical email. Display names live only in
that map; raw bodies stay verbatim; everything you author refers to people by canonical
email or not at all. The dashboard resolves the current identity at render time into an
`acting as` line; ledger decision rows may carry one optional `assignee` key. Both maps are
optional: the plugin renders fully without them.

## Known limitations

- The capture-intent nudge covers interactive sessions; it is not verified to fire under
  headless `-p` runs. Enforcement does not depend on it.
- The budget halt is procedural (skill prose plus the spec's budget line), not a timer.
- The preflight gate resolves specs from the command text; a run launched through an
  indirection it cannot see is gated only by the skill discipline.
- Source-mining adapters beyond the proven slice (repo tree, git history, session JSONL)
  are a documented seam (`templates/sources.yaml`), not shipped code.
- The compiler refuses to price flows containing steps with no measured cost — fill the
  consumer cost table from your own run ledgers first (`templates/cost-table.json`).

## Evals

```
claude plugin eval . --scaffold
```

`--scaffold` is required: each case's `scaffold_script` git-inits a neutral fixture repo.
One suite per skill under `evals/<skill>/<case>/case.yaml`; see `evals/README.md`.

## Changelog

- 0.2.0 — environment health and review flow: the doctor pair
  (`scripts/doctor-classify.py` + `scripts/doctor-remediate.py`, counted H-182/H-183 in the
  source lab — see `docs/doctor.md`), the verdict-forcing review cadence
  (`scripts/review-cadence.py`, counted H-188 — see `docs/review-cadence.md`), the install
  parity checker (`scripts/parity-check.py`, counted H-181), and the advisory waste/flow
  instrument (`scripts/waste-status.py`, uncounted-but-measured; proving specs H-192..H-196
  registered in the source lab). All counted scripts ship byte-preserving from their counted
  fixture copies; only provenance framing and consumer-repo path resolution differ.
- 0.1.0 — first consolidated release: the capture and experiment-loop capabilities of the
  retired predecessor plugins (capture 0.1.4, experiment loop 0.1.0) fold into one
  profile-gated install, joined by the operating-model lifecycle (adopt / observe / evaluate / compile /
  run / verify, the node grammar + Event Modeling layer, the policy interpreter, the
  diagram lane, and the model-to-executable compiler). `/crux:init` migrates repositories
  initialized by the retired plugins.
