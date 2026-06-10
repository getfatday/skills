# document plugin — test suite

The `document` plugin is mostly **skills** — Markdown instructions for an LLM,
which cannot be unit-tested deterministically. Testing therefore splits into
what *is* deterministic (scripts, structure, the factory contract) and what is
not (whether a skill actually *behaves* correctly — that needs LLM-graded
evals). The suite has three layers.

## Layer 1 — script unit tests

Deterministic pytest tests for the plugin's Python scripts, colocated with the
script they cover:

- `scripts/test_derive_events.py` — the git event deriver.
- `skills/document-enrich/scripts/test_enrich.py` — the relationship enricher.

## Layer 2 — contract & structure

Deterministic pytest tests in this directory, enforcing `../FACTORY.md`:

- `test_factory_contract.py` — every skill declares a valid `tier:`; the
  generator emits the full provenance stamp; materialized skills are
  self-sufficient (no `${CLAUDE_PLUGIN_ROOT}`); config schema-version coherence.
- `test_manifests.py` — `plugin.json` / `marketplace.json` / the Cursor mirror
  manifest are valid and consistent; plugin structure is well-formed.

`conftest.py` holds shared fixtures (`plugin_root`, `repo_root`, `frontmatter`).

## Layer 3 — skill evals

Behavioral, LLM-graded tests of skill *behavior*, one `evals.json` per skill
under `skills/<name>/.../`, run through the **skill-creator** plugin's eval
framework. They cost model tokens, so they are **not** part of `make test` —
run them on demand before a release.

## Running the suite

```bash
make test          # Layers 1 + 2 — deterministic, fast, every commit / CI
                   # (runs pytest over clis/ and plugins/document/)
```

Layer 3 evals are run via the skill-creator plugin against a skill's
`evals.json` — see that plugin's documentation. They are not wired into
`make test` because they are non-deterministic and token-costed.

## The `xfail`-until-phase convention

Some Layer-2 tests encode a *target* state the plugin has not reached yet.
They are marked `xfail` with a reason naming the phase that will satisfy them
— e.g. `test_materialized_skill_is_self_sufficient` xfails for
`document-events` and `document-enrich` until Phase 6 of the factory-contract
plan converts them to self-sufficient templates. When that phase lands, its
work removes the marker and the test becomes a normal pass. An `xfail` here
means "known pending", never "known broken".
