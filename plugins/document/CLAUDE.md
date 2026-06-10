# document Plugin

A factory plugin: it generates per-type document-management skills,
commands, and helper scripts into a consuming repository as committed,
self-sufficient files. Read **`FACTORY.md`** (this dir) before proposing or
reviewing a change — it defines the type-vs-instance classification axis,
the artifact tiers, the provenance stamp, the self-sufficiency rule, and
the per-feature checklist.

## Test infrastructure (three layers)

| Layer | Tests what | Where | Tool | Runs |
|---|---|---|---|---|
| 1 — Script units | the plugin's Python scripts | colocated `test_*.py` next to each script | pytest | every commit / CI |
| 2 — Contract & structure | factory-contract compliance, manifests | `plugins/document/tests/` | pytest | every commit / CI |
| 3 — Skill evals | skill *behavior* | `skills/<name>/evals/evals.json` | skill-creator | on-demand |

Run: `make test` (Layers 1+2 — `pytest` honors `testpaths` and skips the
`.cursor/` and `.github/` mirror trees via `norecursedirs`). Layer 3 evals
are non-deterministic and token-costed; run them on-demand, not in CI.

## Test Plan template (required in every plan that produces code)

Per code-producing phase, declare:

- **Layer 1 — script units.** New tests added beside which script; what
  each test asserts. Include any new colocated `test_<script>.py` files.
- **Layer 2 — contract & structure.** New assertions added to
  `test_factory_contract.py` / `test_manifests.py`, or new test modules
  under `tests/`. Note any `xfail` markers and which later phase removes
  them.
- **Layer 3 — evals.** New `evals.json` cases for any new or
  behaviorally-changed skill (under `skills/<name>/evals/`).

If a code-producing phase adds **no tests in any layer**, the plan must
justify why explicitly — never silently.

## The `xfail`-until-phase convention

A test that encodes a target state the plugin has not yet reached is marked
`pytest.mark.xfail(strict=True, reason="<phase> will satisfy this")`. When
the phase lands, its work flips the test to a normal pass; `strict=True`
guarantees the marker cannot silently linger past the phase that was
supposed to satisfy it. An `xfail` here means *known pending*, never
*known broken*.

## Plugin-specific rules

- **Schema-version.** `root.md` and type definitions carry `schema-version`
  (current: **1**, absent = 1). Bumps only on **breaking** schema changes;
  additive changes (a new optional field/section) do not. The plugin's
  supported version is `documentSchemaVersion` in
  `.claude-plugin/plugin.json`. Each step gets an H2 in
  `skills/document-define/references/schema-migrations.md`.
- **Provenance stamps.** Every generated/materialized artifact (skill,
  command, script) carries the full provenance stamp (`factory`,
  `factory-version`, `generated-by`, `generator-version`, `source`,
  `materialized`, `tier`) — see FACTORY.md.
- **Self-sufficiency.** Tier 2-materialized and Tier 3 artifacts may not
  reference `${CLAUDE_PLUGIN_ROOT}`. The `test_template_is_self_sufficient`
  contract test enforces this against every `templates/*/SKILL.md` and its
  colocated `scripts/`.

## Layout

The plugin's *runnable* surface is only the Tier-1 commands. Operational
skills (`lint`, `enrich`, `events`, `verify-inferred`) ship as **templates** —
the plugin doesn't run them directly. A consuming repo runs
`/document:upgrade` to install them as repo-local skills + scripts;
from then on the repo has its own `/document-lint`, `/document-events`, etc.,
and they work with no plugin installed.

```
plugins/document/
  FACTORY.md                                  # factory contract
  CLAUDE.md                                   # this file
  .claude-plugin/plugin.json                  # manifest + documentSchemaVersion
  skills/document-define/                     # Tier 1 — the generator
    references/{type-definition-schema,custom-logic-schema,
                schema-migrations,event-model,inheritance,
                status-transitions}.md
  skills/document-upgrade/                    # Tier 1 — lifecycle command
  commands/{document-define,document-upgrade,
            document-list-types}.md           # Tier 1 commands only
  templates/{document-lint,document-enrich,
             document-events,document-verify-inferred}/   # 2-materialized
    document-events/scripts/derive-events.py + test_derive_events.py
    document-enrich/scripts/enrich.py + test_enrich.py
  scripts/{upgrade-scan.py + test,
           document_validator.py,            # shared guard library
           check-document-edit.py + test,    # PreToolUse — 7 guards
           check-document-staged.py + test,  # pre-commit (materialized)
           check-lint-write.sh,              # PostToolUse advisory
           target_config.py + test,          # .config/documents/rulesync.jsonc reader
           multi_target_emit.py + test,      # rulesync staging + fanout
           materialize.py + test,            # template + githooks + fanout
           inherit-parent-fields.sh}          # Tier 1 plugin scripts
  templates/_root/rulesync.jsonc             # default cross-IDE config
  tests/{conftest.py,test_factory_contract.py,
         test_manifests.py,README.md}          # Layer 2 contract suite
  hooks/hooks.json                             # Tier 1, runtime-registered
```

After a consumer runs `/document:upgrade`, the consuming repo
acquires the materialized form at `.claude/skills/{name}/` and a repo-local
`/{name}` command (unnamespaced — e.g. `/document-events`). The factory
provides the install; the repo runs the materialized form.
