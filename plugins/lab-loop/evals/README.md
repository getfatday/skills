# lab-loop evals

Cases in the `claude plugin eval` format (`evals/<case>/case.yaml`), all with neutral
fixtures: every prompt, path, spec, and scaffolded file is invented for these tests and
carries no content from any particular repository.

## Run

```
claude plugin eval . --scaffold
```

`--scaffold` is required — each case's `scaffold_script` git-inits its fixture repo (the base
plugin's initialized state faked on disk, the spec template, and for the verdict case a
registered spec plus run artifacts). Scaffolds are deterministic: fixed strings only, no
timestamps.

## Cases

| Case | Tests | Kind |
|---|---|---|
| `register-spec-before-run` | Testable idea → spec from the template with one variable, budget, 3–5 binary assertions, verdict rule; no run before the spec | should-act |
| `one-variable-split` | Two variables in one idea → pushback and a split into two comparable single-variable hypotheses | pushback |
| `mechanical-verdict` | Run artifacts with one failed assertion → verdict follows the rule (not the user's impression), run journaled, Runs table updated | should-act |
| `run-gated-without-spec` | Headless run attempt with no registered spec → gated/refused; agent routes back to registration | should-NOT-act guard |

## Grading notes

- Deterministic graders (regex, file_exists) carry the outcome checks; llm rubrics are written
  as concrete checkable claims. Use a sonnet-tier judge (`--judge-model sonnet`).
- `run-gated-without-spec` grants Bash so the PreToolUse gate — not tool absence — is a live
  mechanism under test. Under `--ablation with-without`, the baseline arm is expected to
  attempt the run and fail the `no-run-output` grader; the delta is the gate's measured
  effect.
- The scaffolds fake the lab-intake initialized state (config file plus directories) so
  the journal-fragment steps have a real target without installing the base plugin into the
  eval; the skill prose being tested carries the fragment convention itself.
