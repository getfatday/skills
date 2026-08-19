# lab-intake evals

Cases in the `claude plugin eval` format (`evals/<case>/case.yaml`), all with neutral
fixtures: every prompt, path, and scaffolded file is invented for these tests and carries no
content from any particular repository.

## Run

```
claude plugin eval . --scaffold
```

`--scaffold` is required — each case's `scaffold_script` git-inits its fixture repo (index
seed, directories, and for the guard case a pre-existing raw file). Without it the file-level
graders have nothing to check against. Scaffolds are deterministic: fixed strings only, no
timestamps.

## Cases

| Case | Tests | Kind |
|---|---|---|
| `save-external-finding` | External finding → minimal note with source URL, index line, journal fragment | should-act |
| `self-reference-note` | "Note this for yourself" → durable note under notes/, indexed, journaled | should-act |
| `testable-idea-without-loop` | Testable hunch with no hypothesis skill installed → note tagged `testable`, no fabricated experiment scaffold | conditional branch |
| `raw-write-once` | Direct-edit request against an existing raw file → hook denies; agent explains write-once and offers an alternative | should-NOT-act guard |

## Grading notes

- Deterministic graders (regex, file_exists) carry the outcome checks; llm rubrics are written
  as concrete checkable claims. Use a sonnet-tier judge (`--judge-model sonnet`) — small judges
  miss the refusal-quality nuance in `raw-write-once`.
- `raw-write-once` grants only Edit/Write (no Bash) so the PreToolUse hook — not tool absence —
  is the mechanism under test. Under `--ablation with-without`, the baseline arm is expected to
  edit the file and fail the `raw-file-unchanged` grader; the delta is the guard's measured
  effect.
- The Stop backstop participates naturally in the should-act cases: an agent that skips the
  journal fragment is blocked once with instructions, which is the mechanism working.
