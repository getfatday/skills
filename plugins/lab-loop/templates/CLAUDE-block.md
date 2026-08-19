<!-- BEGIN lab-loop rules (installed by /lab-loop:init; do not hand-edit — re-run init to repair) -->

## Experiment loop

Testable ideas about ways of working run through the lab-loop plugin's `hypothesis` skill
(adapted from, not identical to, Karpathy's autoresearch): spec first, one variable, fixed
budget, binary assertions, mechanical verdict, journaled always.

| Path | Purpose |
|---|---|
| `{{HYPOTHESES_DIR}}/` | One spec per hypothesis: `H-NNN-<slug>.md`, created from `{{TEMPLATE_FILE}}` |
| `{{RUNS_DIR}}/<id>/` | Run artifacts: pinned shared inputs in `fixture/`, per-run outputs in `run-<k>/` |
| `{{PREFLIGHT_FILE}}` | Deterministic spec pre-flight; exit 0 = run-ready |

### Experiment rules

- Every experiment declares 3–5 binary pass/fail assertions BEFORE running. No subjective
  scores.
- One variable per experiment. If a design changes two things, split it into two hypotheses.
- Run the smallest experiment that can falsify the hypothesis; specs follow the template —
  nothing beyond its sections.
- Every run has a fixed budget declared in the spec; halt on breach and record the run as
  budget-exceeded.
- The verdict is keep / discard / refine, decided mechanically from the assertions — never
  from impressions.
- An experiment is done only when its journal fragment records assertions, results, and
  verdict (journal fragments are the lab-intake plugin's write-once convention).
- Surgical scope: an experiment touches only its own spec, its run directory, and its journal
  fragment — never other hypotheses or a human-edited directives file.

<!-- END lab-loop rules -->
