# Ask triage: the finding, and why no gate ships yet

> **NOTHING EXECUTABLE SHIPS FOR THIS.** The ask-triage hook pair exists as calibrated
> reference implementations in the source lab
> (`experiments/runs/H-200/fixture/reference/` — LEG A `ask_gate_ref.py`, LEG B
> `ask_stop_gate_ref.py`, calibrated 7/7 with every seeded defect firing exactly on
> target), and ships **only on a maintainer ruling** (a needs-maintainer item in the source
> lab). This document records the measured finding so the decision is made on evidence.

## What was tested

A two-leg ask gate: a PreToolUse census check on AskUserQuestion (deny a self-servable
throw that carries no options-census record; pass censused genuine-preference asks and
by-law exempt classes) plus a Stop-hook prose-ask net — deterministic, fail-open, graded
mechanically over synthetic payload corpora. The measured motivation: in the source lab's
audited arc, 0/118 asks were agent-originated with a census, 42.3% of audited throws were
fully avoidable, and 73.1% avoidable-or-downgradable.

## The finding: arm-built gate discipline is per-arm variance

Across five counted runs spanning the lineage (H-127 cycles and the fallthrough-complete
H-200 edition), independent builder arms working from the frozen contract:

- **Built the check LOGIC reliably** — the census/dedup/exemption legs went 5-for-5 in
  every run: block/pass/held-out classification held whenever the contract stated it.
- **Failed the SAFETY DISCIPLINE about half the time each** — fail-open on crash and
  exemption-fallthrough ("a failed exemption is a failed shortcut, never itself a deny
  reason") survived teaching only per-arm, even after the fallthrough was stated
  normatively in the contract text. The decisive pair: run 1 followed the explicit
  fallthrough sentence perfectly (5/5); run 2 blocked a trap AGAINST the now-explicit text
  and inverted the taught fail-open behavior (3/5). The verdict closed at discard on the
  third arm-side failure.

No contract wording fixed this — the failure class is variance in the builder, not
ambiguity in the spec (the spec-ambiguity half WAS found and repaired en route: the
unstated fallthrough was a genuine contract gap, the same class as the CI scaffold's
excerpt gap, and repairing it produced one perfect run — but not two).

## The doctrine this yields

**Safety-critical hook discipline ships as fixture-side reference implementations, not
arm-built artifacts.** When the artifact's value is that it fails safe every time, a
per-arm coin flip on fail-open is disqualifying no matter how buildable the happy path is.
The calibrated reference gates — written harness-side, proven 7/7 against the defect
matrix, doors green — are the deliverable that already exists; whether they ship, and with
what maintainer-ratified exemption list and deny wording, is the pending ruling.
Arm-buildability of safety-critical hook discipline returns to the design lane as its own
question.

## Evidence

**H-200-ask-triage-v2** (source lab, discarded 2026-08-28 on the carried arm-side tally;
runs and the aggregate finding recorded in the source lab's journal). The discard is the
finding: it rules out the ship-as-contract-and-let-arms-build-it path for this class, and
routes the reference implementations to the maintainer ruling above. Related keeps this
release DID ship: the directive-intake kit (docs/directive-intake.md) and the preflight
rigor extension (docs/preflight-rigor.md), both of which are deterministic scripts promoted
from counted fixture copies — exactly the shape this finding prescribes.
