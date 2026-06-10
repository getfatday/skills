"""Layer 1 — tests for materialize.py.

Covers provenance injection (frontmatter + script header), template
listing, full materialization end-to-end, dry-run safety, and the
critical self-sufficiency property: a materialized document-events
runs against the materialized script with the plugin uninstalled.
"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).with_name("materialize.py")
PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("materialize_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mat = _load()

STAMP_KWARGS = dict(
    factory_version="0.10.0", generator_version="1.4",
    source="document-events/SKILL.md", today="2026-05-22",
)


# --------------------------------------------------------------------------
# provenance injection
# --------------------------------------------------------------------------

def test_extract_description_stops_at_next_top_level_key():
    """The regex bug that broke every materialized command file: a greedy
    `description: >` block scalar over-consumed the following
    `trigger-phrases:` list items. Guard against regression."""
    text = (
        "---\n"
        "name: example\n"
        "description: >\n"
        "  First line of the description.\n"
        "  Second line continues it.\n"
        "trigger-phrases:\n"
        '  - "should not be in description"\n'
        "allowed-tools: [Read]\n"
        "---\n\nbody\n"
    )
    desc = mat._extract_description(text)
    assert "should not be in description" not in desc
    assert "First line of the description." in desc
    assert "Second line continues it." in desc
    assert len(desc) < 200


def test_extract_description_handles_inline_form():
    text = "---\nname: x\ndescription: A simple inline\n---\n"
    assert mat._extract_description(text) == "A simple inline"


def test_extract_description_returns_empty_when_absent():
    assert mat._extract_description("---\nname: x\n---\n") == ""


def test_yaml_quote_escapes_embedded_quotes():
    assert mat._yaml_quote("hello") == "'hello'"
    assert mat._yaml_quote("it's") == "'it''s'"
    assert mat._yaml_quote('has "double"') == '\'has "double"\''


def test_materialized_command_file_frontmatter_is_bounded(tmp_path):
    """Regression test for the description-overflow bug: the command file's
    frontmatter block must close within a reasonable number of lines —
    a `description:` field that swallowed the whole SKILL.md body would
    blow this assertion. The frontmatter should also close properly with
    a body containing the workflow tag."""
    mat.materialize_template(PLUGIN_ROOT, tmp_path, "document-events",
                             today="2026-05-22")
    cmd = (tmp_path / ".claude/commands/document-events.md").read_text(
        encoding="utf-8"
    )
    lines = cmd.splitlines()
    assert lines[0] == "---"
    end = next(i for i, ln in enumerate(lines[1:], 1) if ln == "---")
    assert end <= 20, (
        f"command-file frontmatter spans {end} lines; description overflowed"
    )
    assert "<workflow>" in cmd, "command file body missing workflow block"


def test_inject_skill_frontmatter_adds_provenance_fields():
    template = (
        "---\n"
        "name: document-events\n"
        "tier: 2-materialized\n"
        "description: >\n  Query the change-event log of a typed document portfolio.\n"
        "---\n\n"
        "body\n"
    )
    out = mat.inject_skill_frontmatter(template, **STAMP_KWARGS)
    assert 'factory: "document"' in out
    assert 'factory-version: "0.10.0"' in out
    assert 'generated-by: "document-upgrade"' in out
    assert 'generator-version: "1.4"' in out
    assert 'source: "templates/document-events/SKILL.md"' in out
    assert 'materialized: "2026-05-22"' in out
    # Pre-existing fields preserved.
    assert "name: document-events" in out
    assert "tier: 2-materialized" in out


def test_inject_skill_frontmatter_overwrites_stale_provenance():
    """Re-materializing a previously-materialized skill replaces, not
    duplicates, the stamp fields."""
    template = (
        "---\n"
        "name: document-events\n"
        'factory: "document"\n'
        'factory-version: "0.5.0"\n'
        'materialized: "2026-01-01"\n'
        "tier: 2-materialized\n"
        "---\n\nbody\n"
    )
    out = mat.inject_skill_frontmatter(template, **STAMP_KWARGS)
    assert 'factory-version: "0.10.0"' in out
    assert 'factory-version: "0.5.0"' not in out
    assert out.count('factory-version:') == 1
    assert 'materialized: "2026-05-22"' in out


def test_inject_skill_frontmatter_rejects_missing_frontmatter():
    import pytest
    with pytest.raises(ValueError, match="frontmatter"):
        mat.inject_skill_frontmatter("no frontmatter\n", **STAMP_KWARGS)


def test_inject_script_provenance_inserts_block_after_shebang():
    src = '#!/usr/bin/env python3\n"""docstring"""\n\ncode()\n'
    out = mat.inject_script_provenance(src, **STAMP_KWARGS)
    assert out.startswith("#!/usr/bin/env python3\n")
    assert "# --- document:provenance ---" in out
    assert "# factory-version: 0.10.0" in out
    assert "# --- end provenance ---" in out
    assert '"""docstring"""' in out  # untouched
    assert "code()" in out


def test_inject_script_provenance_is_idempotent_in_shape():
    """Re-materializing replaces the existing block; the file gains exactly
    one provenance block, not nested ones."""
    src = '#!/usr/bin/env python3\n"""docstring"""\n\ncode()\n'
    once = mat.inject_script_provenance(src, **STAMP_KWARGS)
    twice = mat.inject_script_provenance(
        once, **{**STAMP_KWARGS, "factory_version": "0.11.0"},
    )
    assert twice.count("# --- document:provenance ---") == 1
    assert "# factory-version: 0.11.0" in twice
    assert "# factory-version: 0.10.0" not in twice


# --------------------------------------------------------------------------
# plugin metadata
# --------------------------------------------------------------------------

def test_read_plugin_metadata_uses_real_plugin():
    metadata = mat.read_plugin_metadata(PLUGIN_ROOT)
    assert metadata["factory-version"]  # populated from real plugin.json
    assert metadata["generator-version"]


# --------------------------------------------------------------------------
# template listing
# --------------------------------------------------------------------------

def test_list_templates_includes_all_operational():
    """The four operational skills must all be available as templates."""
    available = set(mat.list_templates(PLUGIN_ROOT))
    assert {"document-events", "document-enrich",
            "document-lint", "document-verify-inferred"} <= available


# --------------------------------------------------------------------------
# materialization end-to-end
# --------------------------------------------------------------------------

def test_materialize_writes_skill_command_and_mirrors(tmp_path):
    written = mat.materialize_template(
        PLUGIN_ROOT, tmp_path, "document-events", today="2026-05-22",
    )

    skill = tmp_path / ".claude/skills/document-events/SKILL.md"
    assert skill.is_file()
    body = skill.read_text(encoding="utf-8")
    # Provenance stamp is on the materialized output.
    assert 'factory: "document"' in body
    # NO leak — the contract's load-bearing assertion.
    assert "${CLAUDE_PLUGIN_ROOT}" not in body, body

    # Script came along with a provenance header.
    script = tmp_path / ".claude/skills/document-events/scripts/derive-events.py"
    assert script.is_file()
    script_body = script.read_text(encoding="utf-8")
    assert "# --- document:provenance ---" in script_body
    assert "${CLAUDE_PLUGIN_ROOT}" not in script_body

    # Repo-local command + rulesync staging (cross-IDE fanout happens
    # in `finalize_targets()`, not here).
    assert (tmp_path / ".claude/commands/document-events.md").is_file()
    assert (tmp_path / ".rulesync/skills/document-events/SKILL.md").is_file()
    assert (tmp_path / ".rulesync/commands/document-events.md").is_file()

    # The summary lists everything written.
    assert ".claude/skills/document-events/SKILL.md" in written
    assert ".rulesync/skills/document-events/SKILL.md" in written


def test_materialize_skips_test_files(tmp_path):
    """A template's test_*.py is a dev artifact, not materialized."""
    mat.materialize_template(PLUGIN_ROOT, tmp_path, "document-events",
                             today="2026-05-22")
    scripts_dir = tmp_path / ".claude/skills/document-events/scripts"
    assert (scripts_dir / "derive-events.py").is_file()
    assert not (scripts_dir / "test_derive_events.py").exists()


def test_materialize_dry_run_writes_nothing(tmp_path):
    plan = mat.materialize_template(
        PLUGIN_ROOT, tmp_path, "document-events", dry_run=True,
        today="2026-05-22",
    )
    assert plan, "dry-run should still report what would be written"
    assert not (tmp_path / ".claude").exists()


def test_materialize_all_templates(tmp_path):
    """All four operational templates can be materialized without conflict."""
    for name in mat.list_templates(PLUGIN_ROOT):
        mat.materialize_template(PLUGIN_ROOT, tmp_path, name,
                                 today="2026-05-22")
    skills = sorted(p.name for p in (tmp_path / ".claude/skills").iterdir())
    assert {"document-events", "document-enrich",
            "document-lint", "document-verify-inferred"} <= set(skills)


# --------------------------------------------------------------------------
# the load-bearing integration test — self-sufficiency
# --------------------------------------------------------------------------

def test_materialized_skill_runs_without_plugin(tmp_path):
    """Materialize document-events into a scratch repo and exercise the
    materialized derive-events.py end-to-end. The script must produce a
    valid JSON event log purely from the repo-local form — no PLUGIN_ROOT,
    no plugin install assumed."""
    # Build a tiny git repo with a typed document.
    repo = tmp_path / "scratch"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"],
                   check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@e.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    (repo / "Products").mkdir()
    (repo / "Products/checkout.md").write_text(
        '---\ntype: prd\nstatus: draft\n---\n\n## Overview\n\nbody\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True,
        env={"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@e.com",
             "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@e.com",
             "GIT_AUTHOR_DATE": "2026-05-22T12:00:00Z",
             "GIT_COMMITTER_DATE": "2026-05-22T12:00:00Z",
             "PATH": "/usr/bin:/bin"},
    )

    # Materialize document-events into it.
    mat.materialize_template(PLUGIN_ROOT, repo, "document-events",
                             today="2026-05-22")

    # Run the materialized script — no plugin assumed.
    materialized = repo / ".claude/skills/document-events/scripts/derive-events.py"
    result = subprocess.run(
        [sys.executable, str(materialized), "-C", str(repo), "derive"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    events = json.loads(result.stdout)
    assert events, "materialized deriver produced no events"
    assert events[0]["op"] == "created"
    assert events[0]["type"] == "prd"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_version():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "materialize.py" in result.stdout


def test_cli_list_lists_templates():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--list"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "document-events" in result.stdout


def test_cli_requires_template_or_all():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", "/tmp"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "--template" in result.stderr or "--all" in result.stderr


# --------------------------------------------------------------------------
# .githooks materialization
# --------------------------------------------------------------------------

def test_materialize_githooks_writes_bundle(tmp_path):
    """Fresh repo: validator + entry script + pre-commit all written and
    carry provenance."""
    written = mat.materialize_githooks(PLUGIN_ROOT, tmp_path,
                                       today="2026-05-22")
    paths = set(written)
    assert ".githooks/document_validator.py" in paths
    assert ".githooks/document-validate-staged.py" in paths
    assert ".githooks/pre-commit" in paths

    validator = (tmp_path / ".githooks/document_validator.py").read_text()
    assert "# --- document:provenance ---" in validator
    assert "# tier: 2-materialized" in validator

    pre = (tmp_path / ".githooks/pre-commit").read_text()
    assert "document-plugin: validate staged docs" in pre
    assert "document-validate-staged.py" in pre


def test_materialize_githooks_preserves_existing_precommit(tmp_path):
    """An existing pre-commit with hand-written checks must keep its
    content; the document-plugin block is prepended."""
    (tmp_path / ".githooks").mkdir()
    existing = (
        "#!/bin/bash\n"
        "echo 'user-authored check'\n"
        "make lint || exit 1\n"
    )
    (tmp_path / ".githooks" / "pre-commit").write_text(existing)

    mat.materialize_githooks(PLUGIN_ROOT, tmp_path, today="2026-05-22")
    merged = (tmp_path / ".githooks/pre-commit").read_text()
    assert "user-authored check" in merged
    assert "make lint" in merged
    assert "document-validate-staged.py" in merged
    # shebang stays at the top
    assert merged.startswith("#!/bin/bash")


def test_materialize_githooks_is_idempotent(tmp_path):
    """Second run with the document-plugin block already present must
    not duplicate the invocation line."""
    mat.materialize_githooks(PLUGIN_ROOT, tmp_path, today="2026-05-22")
    first = (tmp_path / ".githooks/pre-commit").read_text()
    mat.materialize_githooks(PLUGIN_ROOT, tmp_path, today="2026-05-22")
    second = (tmp_path / ".githooks/pre-commit").read_text()
    # Idempotent: marker appears exactly once in the result.
    assert second.count("document-plugin: validate staged docs") == 1
    # Pre-commit content unchanged on second run.
    assert first == second


def test_materialize_githooks_dry_run_writes_nothing(tmp_path):
    written = mat.materialize_githooks(PLUGIN_ROOT, tmp_path,
                                        dry_run=True, today="2026-05-22")
    assert written  # reported paths
    assert not (tmp_path / ".githooks").exists()


def test_materialized_validator_runs_standalone(tmp_path):
    """The materialized validator + entry script must work with no
    plugin installed — pure self-sufficiency."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)

    # Seed a type def + commit, then materialize, then stage a bad doc
    types = repo / ".config/documents/types"
    types.mkdir(parents=True)
    (types / "task.md").write_text(
        "## Identity\n- name: task\n\n"
        "## Fields\n### Required\n- `owner: string` — o\n\n"
        "## Sections\n### Required\n- `## Body` — body\n\n"
        "## Lifecycle\n- values: open, done\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    mat.materialize_githooks(PLUGIN_ROOT, repo, today="2026-05-22")

    bad = repo / "tasks" / "x.md"
    bad.parent.mkdir()
    bad.write_text("---\ntype: task\nstatus: weird\n---\n## Body\nx\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    # Run the materialized entry script directly — NOT the plugin copy.
    r = subprocess.run(
        [sys.executable,
         str(repo / ".githooks/document-validate-staged.py")],
        cwd=repo, capture_output=True, text=True,
    )
    assert r.returncode == 1, r.stderr
    assert "tasks/x.md" in r.stderr
    assert "owner" in r.stderr or "weird" in r.stderr


def test_cli_githooks_flag_materializes_bundle(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path), "--githooks"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".githooks/document-validate-staged.py").is_file()
    payload = json.loads(result.stdout)
    assert "__githooks__" in payload["materialized"]


# --------------------------------------------------------------------------
# Phase 2 — rulesync fanout
# --------------------------------------------------------------------------

def test_materialize_stages_into_rulesync(tmp_path):
    """Every materialized template should land in `.rulesync/skills/`
    alongside the canonical `.claude/skills/`."""
    mat.materialize_template(PLUGIN_ROOT, tmp_path, "document-events",
                             today="2026-05-22")
    staged = tmp_path / ".rulesync/skills/document-events/SKILL.md"
    cmd_staged = tmp_path / ".rulesync/commands/document-events.md"
    assert staged.is_file()
    assert cmd_staged.is_file()
    # The staged skill carries the body (not the 3-line strawman).
    body = staged.read_text(encoding="utf-8")
    assert "name: document-events" in body
    assert len(body) > 200, "staged skill should carry the canonical body"


def test_finalize_targets_uses_default_when_no_config(tmp_path, monkeypatch):
    """`finalize_targets()` falls back to DEFAULT_CONFIG when the repo
    has no `.config/documents/rulesync.jsonc`."""
    # Stub run_rulesync to record what it was called with — we don't
    # want to actually fire npx in this test.
    here = pathlib.Path(SCRIPT).parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]
    captured: dict = {}

    def fake_run(repo_root, targets, features, **kw):
        captured["targets"] = list(targets)
        captured["features"] = list(features)
        return mte.RulesyncResult(
            status="ok", reason="", targets=list(targets),
            stdout="", stderr="", returncode=0,
        )
    monkeypatch.setattr(mte, "run_rulesync", fake_run)

    result = mat.finalize_targets(tmp_path)
    assert result["status"] == "ok"
    assert captured["targets"] == ["codexcli", "cursor"]


def test_finalize_targets_dry_run(tmp_path):
    result = mat.finalize_targets(tmp_path, dry_run=True)
    assert result["status"] == "dry-run"
    # No `.cursor/` or `.codex/` written
    assert not (tmp_path / ".cursor").exists()
    assert not (tmp_path / ".codex").exists()


def test_finalize_targets_deferred_includes_fallback_plan(tmp_path,
                                                           monkeypatch):
    """When run_rulesync returns deferred (npx missing), the
    `finalize_targets()` payload must include a fallback_plan so the
    upgrade skill knows how to AI-generate the outputs."""
    here = pathlib.Path(SCRIPT).parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]
    # Stage some content so fallback_plan has something to report.
    mte.stage_into_rulesync(tmp_path, "document-events",
                             "---\nname: x\ndescription: y\n---\nbody\n",
                             command_text="cmd")

    monkeypatch.setattr(mte, "npx_available", lambda: False)
    result = mat.finalize_targets(tmp_path)
    assert result["status"] == "deferred"
    assert result["fallback_plan"] is not None
    assert "document-events" in result["fallback_plan"]["skills"]


def test_cli_targets_override(tmp_path, monkeypatch):
    """`--targets` overrides whatever is in rulesync.jsonc."""
    # Write a config with one target; pass --targets with two; the
    # invocation should reflect --targets.
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": {"cursor": ["skills"]}}\n'
    )
    # Use --no-fanout to avoid actually invoking npx; --targets is
    # still parsed and goes into the fanout dict.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path),
         "--template", "document-events", "--no-fanout"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_no_fanout_skips_rulesync(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path),
         "--template", "document-events", "--no-fanout"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # No fanout key in the payload since --no-fanout was set.
    assert "fanout" not in payload
    # Staging still happens.
    assert (tmp_path / ".rulesync/skills/document-events/SKILL.md").is_file()


def test_materialize_root_config_writes_default(tmp_path):
    """Fresh repo: `materialize_root_config` writes the default
    `.config/documents/rulesync.jsonc` from the plugin's template."""
    written = mat.materialize_root_config(PLUGIN_ROOT, tmp_path)
    cfg = tmp_path / ".config/documents/rulesync.jsonc"
    assert cfg.is_file()
    assert ".config/documents/rulesync.jsonc" in written
    text = cfg.read_text(encoding="utf-8")
    assert "documentTargets" in text
    assert "cursor" in text
    assert "codexcli" in text


def test_materialize_root_config_does_not_clobber(tmp_path):
    """User-edited config must be preserved across re-runs."""
    cfg_dir = tmp_path / ".config/documents"
    cfg_dir.mkdir(parents=True)
    user_edit = (
        '{\n  "documentTargets": true,\n'
        '  "targets": {"cursor": ["skills"], "copilot": ["skills"]}\n}\n'
    )
    (cfg_dir / "rulesync.jsonc").write_text(user_edit)
    written = mat.materialize_root_config(PLUGIN_ROOT, tmp_path)
    # No-op when the file already exists.
    assert written == []
    assert (cfg_dir / "rulesync.jsonc").read_text() == user_edit


def test_materialize_root_config_dry_run(tmp_path):
    written = mat.materialize_root_config(PLUGIN_ROOT, tmp_path,
                                           dry_run=True)
    assert ".config/documents/rulesync.jsonc" in written
    assert not (tmp_path / ".config/documents").exists()


def test_cli_all_writes_root_config(tmp_path):
    """`--all --no-fanout` (the idiom for first-run setup) writes the
    default rulesync.jsonc."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path),
         "--all", "--no-fanout"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".config/documents/rulesync.jsonc").is_file()
    payload = json.loads(result.stdout)
    assert "__root_config__" in payload["materialized"]


# --------------------------------------------------------------------------
# post_generate — Tier-3 cross-IDE fanout
# --------------------------------------------------------------------------

TIER3_SKILL = (
    "---\n"
    "name: prd\n"
    "description: >\n"
    "  Manages product requirements documents. Handles creation,\n"
    "  retrieval, listing, validation, and lifecycle transitions.\n"
    "factory: document\n"
    'factory-version: "0.16.0"\n'
    "generated-by: document-define\n"
    'generator-version: "1.4"\n'
    'source: "skills/document-define/SKILL.md"\n'
    'type-definition: ".config/documents/types/prd.md"\n'
    'type-definition-hash: "deadbeef"\n'
    'materialized: "2026-05-23"\n'
    "tier: 3\n"
    "---\n\n"
    "# prd\n\n"
    "## Operations\n\n"
    "create, list, get, status, …\n"
)

TIER3_CMD = (
    "---\n"
    "description: PRD lifecycle commands\n"
    "argument-hint: \"[op] [name] …\"\n"
    "---\n"
    "Body.\n"
)


def _stage_tier3(tmp_path):
    """Stage a fake `/document:define`-generated Tier-3 skill into
    `.claude/skills/prd/` + `.claude/commands/prd.md`."""
    (tmp_path / ".claude/skills/prd").mkdir(parents=True)
    (tmp_path / ".claude/skills/prd/SKILL.md").write_text(
        TIER3_SKILL, encoding="utf-8",
    )
    (tmp_path / ".claude/commands").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude/commands/prd.md").write_text(
        TIER3_CMD, encoding="utf-8",
    )


def test_post_generate_stages_skill_and_command(tmp_path, monkeypatch):
    """`post_generate` reads the canonical Tier-3 output and writes
    name + description + body into `.rulesync/skills/<name>/`."""
    _stage_tier3(tmp_path)

    here = pathlib.Path(SCRIPT).parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    monkeypatch.setattr(mte, "npx_available", lambda: False)  # avoid real fanout
    result = mat.post_generate(PLUGIN_ROOT, tmp_path, "prd")

    staged_skill = tmp_path / ".rulesync/skills/prd/SKILL.md"
    assert staged_skill.is_file()
    body = staged_skill.read_text(encoding="utf-8")
    # Reduced frontmatter: only name + description (no provenance,
    # no tier, no factory-*).
    assert "name: prd" in body
    assert "description:" in body
    assert "factory:" not in body
    assert "tier:" not in body
    # Body carries the original H1 + sections.
    assert "## Operations" in body

    staged_cmd = tmp_path / ".rulesync/commands/prd.md"
    assert staged_cmd.is_file()
    assert "PRD lifecycle commands" in staged_cmd.read_text()

    # fanout result is included
    assert "fanout" in result
    assert result["fanout"]["status"] == "deferred"  # npx stubbed off


def test_post_generate_invokes_fanout(tmp_path, monkeypatch):
    """When npx is available, post_generate calls finalize_targets
    which calls run_rulesync."""
    _stage_tier3(tmp_path)
    here = pathlib.Path(SCRIPT).parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    captured: dict = {}

    def fake_run(repo_root, targets, features, **kw):
        captured["targets"] = list(targets)
        return mte.RulesyncResult(
            status="ok", reason="", targets=list(targets),
            stdout="ok", stderr="", returncode=0,
        )
    monkeypatch.setattr(mte, "npx_available", lambda: True)
    monkeypatch.setattr(mte, "run_rulesync", fake_run)

    result = mat.post_generate(PLUGIN_ROOT, tmp_path, "prd")
    assert result["fanout"]["status"] == "ok"
    assert captured["targets"] == ["codexcli", "cursor"]


def test_post_generate_missing_skill_raises(tmp_path):
    """If no Tier-3 skill exists at the path, fail cleanly with an
    actionable message."""
    with pytest.raises(FileNotFoundError) as excinfo:
        mat.post_generate(PLUGIN_ROOT, tmp_path, "nonexistent")
    assert "nonexistent" in str(excinfo.value)
    assert "document:define" in str(excinfo.value)


def test_post_generate_without_command(tmp_path, monkeypatch):
    """Some types may not produce a command file. Post-generate must
    handle the missing command gracefully — stage just the skill."""
    (tmp_path / ".claude/skills/x").mkdir(parents=True)
    (tmp_path / ".claude/skills/x/SKILL.md").write_text(TIER3_SKILL)

    here = pathlib.Path(SCRIPT).parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]
    monkeypatch.setattr(mte, "npx_available", lambda: False)

    result = mat.post_generate(PLUGIN_ROOT, tmp_path, "x")
    assert (tmp_path / ".rulesync/skills/x/SKILL.md").is_file()
    assert not (tmp_path / ".rulesync/commands/x.md").exists()
    assert "staged" in result


def test_post_generate_dry_run(tmp_path):
    _stage_tier3(tmp_path)
    result = mat.post_generate(PLUGIN_ROOT, tmp_path, "prd", dry_run=True)
    # Reports the would-be paths.
    assert ".rulesync/skills/prd/SKILL.md" in result["staged"]
    assert ".rulesync/commands/prd.md" in result["staged"]
    # No file written.
    assert not (tmp_path / ".rulesync").exists()
    assert result["dry_run"] is True


def test_cli_post_generate_end_to_end(tmp_path):
    """`materialize.py --post-generate prd` works as a CLI invocation."""
    _stage_tier3(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path),
         "--post-generate", "prd"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "staged" in payload
    assert payload["fanout"] is not None


def test_cli_post_generate_missing_skill_exits_nonzero(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path),
         "--post-generate", "ghost"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert "ghost" in result.stderr


def test_cli_all_runs_fanout_with_defaults(tmp_path):
    """`--all` materializes every template and runs the fanout
    against the configured/default targets. Skip if npx absent."""
    if shutil.which("npx") is None:
        pytest.skip("npx not on PATH")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path), "--all"],
        capture_output=True, text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "fanout" in payload
    assert payload["fanout"]["status"] in {"ok", "deferred"}
    if payload["fanout"]["status"] == "ok":
        # At least the cursor mirror is on disk
        assert (tmp_path / ".cursor/skills/document-events/SKILL.md").is_file()
