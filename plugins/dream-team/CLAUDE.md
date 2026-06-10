# dream-team Plugin

A factory plugin: it generates per-team-member skills, the team-assemble
engine, the orchestrator agent, the entry commands, and helper scripts into a
consuming repository as committed, self-sufficient files. Read **`FACTORY.md`**
(this dir) before proposing or reviewing a change — it defines the
team-member-vs-consultation classification axis, the artifact tiers, the
provenance stamp, the self-sufficiency rule, and the per-feature checklist.

## Test infrastructure (three layers)

| Layer | Tests what | Where | Tool | Runs |
|---|---|---|---|---|
| 1 — Script units | the plugin's Python scripts | colocated `test_*.py` next to each script | pytest | every commit / CI |
| 2 — Contract & structure | factory-contract compliance, manifests | `plugins/dream-team/tests/` | pytest | every commit / CI |
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

- **Schema-version.** `.config/team/root.md` and blueprints carry
  `schema-version` (current: **1**, absent = 1). Bumps only on **breaking**
  schema changes; additive changes (a new optional field/section) do not.
  The plugin's supported version is `dreamTeamSchemaVersion` in
  `.claude-plugin/plugin.json`. Each step gets an H2 in
  `skills/team-member-recruit/references/schema-migrations.md`.
- **Provenance stamps.** Every generated/materialized artifact (skill,
  command, agent, script) carries the full provenance stamp (`factory`,
  `factory-version`, `generated-by`, `generator-version`, `source`,
  `materialized`, `tier`, plus `blueprint`/`blueprint-hash` for Tier 3) —
  see FACTORY.md.
- **Self-sufficiency.** Tier 2-materialized and Tier 3 artifacts may not
  reference `${CLAUDE_PLUGIN_ROOT}`. The `test_template_is_self_sufficient`
  contract test enforces this against every `templates/*/SKILL.md` (and
  agent / command equivalents) and its colocated `scripts/`.
- **Pattern bundle integrity.** The 10 conversation patterns + `router.md`
  + `primitives.md` materialize as one bundle under
  `.claude/skills/team-assemble/patterns/`. The orchestrator agent reads
  them via repo-relative path from team-assemble. Patterns do not
  materialize independently and must not be referenced as
  `${CLAUDE_PLUGIN_ROOT}/patterns/` from materialized artifacts.
- **`<extends>` rewriting.** Persona skills `<extends>` shared team
  knowledge (e.g. Beck's skill extends team-engineering). The materializer
  rewrites these from plugin-relative paths
  (`team-engineering/skills/engineering/SKILL.md`) to consumer-relative
  paths (`team-engineering/SKILL.md` under `.claude/skills/`).

## Layout

The plugin's *runnable* surface is only the Tier-1 commands. Operational
artifacts (team-assemble, orchestrator, the 4 entry commands) ship as
**templates** — the plugin doesn't run them directly. A consuming repo
runs `/dream-team:recruit` (first-time) or `/dream-team:update` to install
them as repo-local artifacts; from then on the repo has its own `/consult`,
`/coach`, `/plan`, `/review`, `.claude/skills/team-assemble/`, and
`.claude/agents/orchestrator.md`, and they work with no plugin installed.

```
plugins/dream-team/
  FACTORY.md                                  # factory contract
  CLAUDE.md                                   # this file
  .claude-plugin/plugin.json                  # manifest + dreamTeamSchemaVersion
  skills/team-member-recruit/                 # Tier 1 — the generator
    references/{team-member-blueprint-schema,team-blueprint-schema,
                research-engine,schema-migrations,
                operational-skill-template-spec}.md
  skills/team-update/                         # Tier 1 — lifecycle command
  skills/team-roster/                         # Tier 1 — status reporter
  skills/team-member-add/                     # Tier 1 — install from factory library
  skills/team-member-update/                  # Tier 1 — research-driven enrichment
  skills/team-member-remove/                  # Tier 1 — uninstall + cleanup
  commands/{recruit,update,roster}.md         # Tier 1 commands only
  templates/team-assemble/                    # 2-materialized — workflow engine
    SKILL.md
    patterns/{map-reduce,sequential,supervisor,hierarchical,debate,
              blackboard,voting,reflection,moe-routing,round-robin,
              router,primitives}.md
  templates/orchestrator/                     # 2-materialized — team lead agent
    orchestrator.md
  templates/team-commands/                    # 2-materialized — entry commands
    consult/consult.md
    coach/coach.md
    plan/plan.md
    review/review.md
  templates/team-members/                     # 3 — per-member factory library
    kent-beck/ ... marty-cagan/ ...
  templates/teams/                            # 3 — per-team factory library
    engineering/ product/
  templates/_root/rulesync.jsonc              # default cross-IDE config
  scripts/{materialize.py + test,
           target_emit.py + test,             # Claude/Cursor/Copilot transforms
           team_member_validator.py,          # shared guard library
           check-generated-edit.py + test,    # PreToolUse — blueprint integrity
           check-blueprint-staged.py + test,  # pre-commit (materialized)
           upgrade-scan.py + test,            # provenance-stamp discovery
           check-factory-contract.py}         # CI enforcement
  tests/{conftest.py,test_factory_contract.py,
         test_manifests.py,README.md}          # Layer 2 contract suite
  hooks/hooks.json                             # Tier 1, runtime-registered
  marketplace.json                             # factory catalog of team-members + teams
  examples/team-member-example/                # reference for factory contributors
```

After a consumer runs `/dream-team:recruit "Kent Beck"` (or any first-time
factory command), the consuming repo acquires:

- `.config/team/root.md` (roster manifest)
- `.config/team/team-members/kent-beck.md` (blueprint)
- `.claude/skills/kent-beck/SKILL.md` (materialized persona)
- `.claude/skills/team-assemble/SKILL.md` + `patterns/` (workflow engine)
- `.claude/agents/orchestrator.md` (team lead)
- `.claude/commands/{consult,coach,plan,review}.md` (entry verbs)

The factory provides the install; the repo runs the materialized form.

## Naming conventions

- **Skill / command file names** match their slug (e.g. `skills/team-member-recruit/SKILL.md`).
- **Factory commands** are namespaced under `/dream-team:` (e.g. `/dream-team:recruit`).
- **Materialized entry commands** are not namespaced (e.g. `/consult`).
- **Team-member slugs** are kebab-cased full names (`kent-beck`, `marty-cagan`).
- **Team slugs** are domain names (`engineering`, `product`).
- **Materialized team skills** prefix the slug with `team-` to disambiguate
  from members (`.claude/skills/team-engineering/SKILL.md`).
