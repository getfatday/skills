# lab-loop

Hypothesis-driven experiments for any repo: every idea becomes a spec with 3–5 binary pass/fail
assertions BEFORE anything runs; fixed budgets with halt-on-breach; verdicts
(keep/discard/refine) decided mechanically from assertions; every run journaled, including
failures. A deterministic preflight gates runs. Requires lab-intake (the journal and
capture discipline live there).

**Scope.** This is an experiment discipline for ways of working — spec first, one variable,
binary evaluation — not a task tracker or a CI system. The loop's outputs are hypothesis specs,
run artifacts, and journal fragments; capture and the journal itself belong to the base plugin.

## Provenance

The loop is adapted from — not identical to — Andrej Karpathy's autoresearch, whose loop is
simply: modify, train five minutes, check improvement, keep or discard, repeat. The
spec/assertion/budget/verdict machinery is this plugin's design, not Karpathy's.

## Requirements

`lab-intake` (>= 0.1.0) must be installed and initialized (`/lab-intake:init`) before
this plugin's init will scaffold anything: the journal fragments the loop writes and the
capture step that registration routes through both live in the base. The dependency is declared
in this plugin's manifest; `/lab-loop:init` also checks at runtime and refuses with
instructions when the base is absent.

## Quick start

1. Install lab-intake and this plugin (from your marketplace, or load checkouts directly
   with `claude --plugin-dir <path-to>/lab-intake --plugin-dir <path-to>/lab-loop`).
2. In your repository, run `/lab-intake:init`, then `/lab-loop:init`. The loop
   scaffold creates the hypotheses and runs directories, installs the spec template and the
   deterministic preflight, and extends CLAUDE.md with the experiment rules block — then commit
   the scaffold.
3. Say "test whether X actually works". The `hypothesis` skill runs the loop: spec before
   anything runs, one variable, fixed budget, 3–5 binary assertions, mechanical verdict,
   journaled always.

## The loop

1. **Spec** — register `hypotheses/H-NNN-<slug>.md` from the template: one falsifiable
   sentence, exactly one variable under test, a baseline, a fixed budget per run, 3–5 binary
   assertions, a mechanical verdict rule. Registering a spec is itself a capture, journaled
   through the base plugin's fragment discipline.
2. **Preflight** — `python3 experiments/preflight.py hypotheses/H-NNN-<slug>.md` runs the
   deterministic checks (required sections, two-way-door method, sandboxing, ground-truth
   isolation, freeze language, budget line, mapped scope exclusions, assertion count,
   mechanical verdict rule). Exit 0 = run-ready; nonzero = fix or escalate.
3. **Run within budget** — artifacts land in `experiments/runs/<id>/run-<k>/`; pinned inputs
   both arms share live in `experiments/runs/<id>/fixture/`. Halt on budget breach and record
   the run as budget-exceeded.
4. **Evaluate mechanically** — each assertion gets pass/fail plus one line of evidence; the
   spec's verdict rule is applied literally, never overridden by impressions.
5. **Journal always** — one write-once fragment per run (`type: run`) via the base plugin's
   journal discipline; update the spec's Status and Runs table.

## What ships

| Component | Purpose |
|---|---|
| `skills/hypothesis/` | The full loop: spec, preflight, budgeted run, binary evaluation, mechanical verdict, journal |
| `skills/init/` | User-invoked scaffold (refuses without the base; idempotent) |
| `hooks/hooks.json` + `hooks/scripts/` | Deterministic guards (see table below) |
| `scripts/preflight.py` | The deterministic spec preflight (copied into your repo by init; also run by the gate) |
| `scripts/init-scaffold.py` | The deterministic scaffold init runs |
| `templates/` | Canonical copies of everything init writes |
| `evals/` | Eval cases for `claude plugin eval` (neutral fixtures) |

## The three layers

A plugin cannot inject project memory or permission rules into a consumer repository, so every
mechanism ships three ways:

1. **Hooks** — deterministic guards, active while the plugin is enabled.
2. **Durable repository artifacts** — written into your repo by `init`: the spec template, the
   installed preflight script, and the CLAUDE.md experiment-rules block. These survive a plugin
   disable.
3. **Skill prose** — the procedure itself, in the `hypothesis` skill.

## Hooks

| Event | Behavior |
|---|---|
| PreToolUse (`Bash`, run-shaped) | Preflight gate: headless agent invocations (`claude -p` / `--print`) that reference a hypothesis spec or a runs-directory path are denied when the spec is missing or fails the shipped preflight. Reads, plumbing, and everything else pass through; internal errors fail open. |
| PreToolUse (`Bash`, `git commit`) | Advisory backstop: a tinker-shaped commit (tinker verbs in the message, or scratch/tmp/experiment/probe-named new files) with no hypothesis spec staged prints a one-line nudge toward registering a spec. Always exits 0 — never blocks. |

All hook scripts are stdlib-only Python, fail open on any error, and use consumer-generic paths.

## Configuration

`init` writes `.claude/lab-loop.json` at your repo root; the hooks, the skill, and the
scaffold read it. All paths are repo-relative. Journal paths come from the base plugin's
`.claude/lab-intake.json`.

| Key | Default |
|---|---|
| `hypotheses_dir` | `hypotheses` |
| `runs_dir` | `experiments/runs` |
| `template_file` | `hypotheses/TEMPLATE.md` |
| `preflight_file` | `experiments/preflight.py` |

## Known limitations

- The budget halt is procedural (skill prose plus the spec's budget line), not a timer: the
  agent stops and records budget-exceeded; nothing kills a running process at the boundary.
- Assertions must be written so their evidence is mechanically checkable; the skill requires
  rewriting them until they are, but grading still happens in-session rather than by a runner.
- The commit backstop reads the staged tree and the repository's last commit-message file at
  hook time, so message-based detection can lag one commit behind when committing with `-m`;
  the staged-filename signal does not lag. It is advisory either way.
- The preflight gate resolves specs from the command text; a run launched through an
  indirection it cannot see (a script that itself invokes the runner) is gated only by the
  skill discipline.
- Cross-plugin routing (a captured testable idea graduating into a spec here) is agent
  judgment guided by skill prose, not a wired automation.

## Evals

```
claude plugin eval . --scaffold
```

`--scaffold` is required: each case's `scaffold_script` git-inits a neutral fixture repo with
the base plugin's initialized state faked on disk. The `run-gated-without-spec` case is the
should-NOT-act guard test — it passes only when no run output exists and the agent routes back
to spec registration.
