# dream-team tests

Three layers, two of which run on every commit.

## Layer 1 — script units

Colocated `test_*.py` next to each Python script under `plugins/dream-team/scripts/`.
Pytest discovers them via the repo-root `pyproject.toml` `testpaths`. Run with
`make test` from the repo root.

## Layer 2 — contract & structure (this directory)

- `test_factory_contract.py` — enforces `FACTORY.md`: every skill declares a
  valid `tier:`; every materializable template carries the full provenance
  stamp; no `${CLAUDE_PLUGIN_ROOT}` or `plugins/` path leaks into a
  materializable template; the materializer script exists; the integrity
  hook is wired.
- `test_manifests.py` — `.claude-plugin/plugin.json` is valid and declares
  `dreamTeamSchemaVersion`; the cursor mirror agrees on name and version
  (catches missed `rulesync.sh` runs); the factory's marketplace catalog
  has matching blueprints under `templates/team-members/` and
  `templates/teams/`; skill frontmatter `name:` matches the directory name.

Run with `make test` (Layer 1 + Layer 2 together).

### xfail-until-phase convention

Tests that encode a target state the plugin has not yet reached are marked
`pytest.mark.xfail(strict=True, reason="<phase> will satisfy this")`. When
the phase lands, its work flips the test to a normal pass; `strict=True`
guarantees the marker cannot silently linger past the phase that was supposed
to satisfy it.

Current `xfail`s:
- `test_materialized_templates_present` — flips in Phase 2c when
  `templates/team-assemble/`, `templates/orchestrator/`, and
  `templates/team-commands/{verb}/` land.
- `test_template_carries_provenance_stamp` — Phase 2c stamps each template.
- `test_template_is_self_sufficient` — Phase 2c writes templates that pass
  the self-sufficiency rule.
- `test_materializer_script_present` — Phase 2d ports `materialize.py` from
  the document plugin.
- `test_ci_factory_contract_check_present` — Phase 2d adds the CI helper.
- `test_pretooluse_hook_present` — Phase 6 adds the integrity hook bundle.

## Layer 3 — skill evals

Per-skill `evals/evals.json` files driven by skill-creator. Non-deterministic
and token-costed — run on-demand, not in CI.
