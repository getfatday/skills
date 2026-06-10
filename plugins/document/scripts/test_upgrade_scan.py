"""Layer 1 — tests for upgrade-scan.py.

Covers the deterministic core that `/document:upgrade`'s skill consumes:
provenance parsing (three serializations), version comparison,
classification (current / stale / orphan / ahead / detached / malformed /
untracked / migration-needed), and the end-to-end scan over a scratch repo.
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).with_name("upgrade-scan.py")
PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("upgrade_scan", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


us = _load()


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

SKILL_TEXT = """---
name: prd
factory: document
factory-version: "0.8.0"
generated-by: document-define
generator-version: "1.4"
source: "skills/document-define/SKILL.md"
type-definition: ".config/documents/types/prd.md"
type-definition-hash: "deadbeef"
materialized: "2026-05-22"
tier: 3
---

body
"""


def test_parse_skill_frontmatter():
    fields = us.parse_skill_frontmatter(SKILL_TEXT)
    assert fields["factory"] == "document"
    assert fields["factory-version"] == "0.8.0"
    assert fields["type-definition-hash"] == "deadbeef"
    assert fields["tier"] == "3"


def test_parse_skill_frontmatter_no_factory_returns_empty():
    """A skill without a `factory: document` stamp is not a materialized
    document-plugin artifact."""
    assert us.parse_skill_frontmatter("---\nname: other\n---\n\n") == {}


def test_parse_skill_frontmatter_no_frontmatter():
    assert us.parse_skill_frontmatter("just a body\n") == {}


SCRIPT_TEXT = """#!/usr/bin/env python3
# --- document:provenance ---
# factory: document
# factory-version: 0.8.0
# generated-by: document-upgrade
# generator-version: 1.4
# source: scripts/derive-events.py
# materialized: 2026-05-22
# tier: 2-materialized
# --- end provenance ---
\"\"\"the actual script\"\"\"
"""


def test_parse_script_provenance():
    fields = us.parse_script_provenance(SCRIPT_TEXT)
    assert fields["factory"] == "document"
    assert fields["tier"] == "2-materialized"
    assert fields["source"] == "scripts/derive-events.py"


def test_parse_script_provenance_no_block():
    assert us.parse_script_provenance("#!/usr/bin/env python3\n\nprint('hi')\n") == {}


def test_parse_config_schema_version():
    root_md = ("# Document Root\n\n## Configuration\n"
               "- root-type: project\n- schema-version: 2\n")
    assert us.parse_config_schema_version(root_md) == 2


def test_parse_config_schema_version_absent_is_none():
    """Absent = caller treats as version 1, but the parser returns None so
    'not recorded' and 'recorded as 1' stay distinguishable."""
    assert us.parse_config_schema_version("# Type\n\n## Identity\n- name: x\n") is None


# --------------------------------------------------------------------------
# classification — skills (Tier 3)
# --------------------------------------------------------------------------

INSTALLED = {
    "factory-version": "0.8.0",
    "generator-version": "1.4",
    "document-schema-version": 1,
}


def _write_prd_artifacts(repo, *, factory_version="0.8.0",
                        generator_version="1.4", hash_match=True):
    """Write a paired type-def + generated Tier-3 skill into `repo` and
    return the skill path. Hash on the stamp matches the type-def file by
    default; flip `hash_match=False` to record a wrong hash."""
    (repo / ".config/documents/types").mkdir(parents=True, exist_ok=True)
    type_def = repo / ".config/documents/types/prd.md"
    type_def.write_text("# PRD\n\n## Identity\n- name: prd\n", encoding="utf-8")
    correct = hashlib.sha256(type_def.read_bytes()).hexdigest()
    recorded = correct if hash_match else "0" * 64

    (repo / ".claude/skills/prd").mkdir(parents=True, exist_ok=True)
    skill = repo / ".claude/skills/prd/SKILL.md"
    skill.write_text(
        "---\n"
        "name: prd\n"
        "factory: document\n"
        f'factory-version: "{factory_version}"\n'
        "generated-by: document-define\n"
        f'generator-version: "{generator_version}"\n'
        'source: "skills/document-define/SKILL.md"\n'
        'type-definition: ".config/documents/types/prd.md"\n'
        f'type-definition-hash: "{recorded}"\n'
        'materialized: "2026-05-22"\n'
        "tier: 3\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    return skill


def _classify(repo, skill):
    text = skill.read_text(encoding="utf-8")
    return us.classify_artifact("skill", skill, text, repo, INSTALLED)


def test_classify_current_skill(tmp_path):
    skill = _write_prd_artifacts(tmp_path)
    assert _classify(tmp_path, skill)["classification"] == "current"


def test_classify_stale_factory_version(tmp_path):
    skill = _write_prd_artifacts(tmp_path, factory_version="0.7.0")
    result = _classify(tmp_path, skill)
    assert result["classification"] == "stale"
    assert any("factory-version" in r for r in result["reasons"])


def test_classify_stale_generator_version(tmp_path):
    skill = _write_prd_artifacts(tmp_path, generator_version="1.3")
    result = _classify(tmp_path, skill)
    assert result["classification"] == "stale"
    assert any("generator-version" in r for r in result["reasons"])


def test_classify_stale_type_def_hash_drift(tmp_path):
    skill = _write_prd_artifacts(tmp_path, hash_match=False)
    result = _classify(tmp_path, skill)
    assert result["classification"] == "stale"
    assert any("type-definition-hash" in r for r in result["reasons"])


def test_classify_ahead_factory_version(tmp_path):
    skill = _write_prd_artifacts(tmp_path, factory_version="0.9.0")
    result = _classify(tmp_path, skill)
    assert result["classification"] == "ahead"


def test_classify_orphan_when_type_def_missing(tmp_path):
    skill = _write_prd_artifacts(tmp_path)
    (tmp_path / ".config/documents/types/prd.md").unlink()
    result = _classify(tmp_path, skill)
    assert result["classification"] == "orphan"


def test_classify_detached_skips(tmp_path):
    skill = _write_prd_artifacts(tmp_path)
    skill.write_text(skill.read_text(encoding="utf-8").replace(
        "tier: 3", "tier: 3\nprovenance: detached"), encoding="utf-8")
    assert _classify(tmp_path, skill)["classification"] == "detached"


def test_classify_malformed_skill(tmp_path):
    (tmp_path / ".claude/skills/x").mkdir(parents=True)
    skill = tmp_path / ".claude/skills/x/SKILL.md"
    skill.write_text("---\nname: x\nfactory: document\n---\n", encoding="utf-8")
    result = us.classify_artifact(
        "skill", skill, skill.read_text(encoding="utf-8"), tmp_path, INSTALLED,
    )
    assert result["classification"] == "malformed"


def test_classify_untracked_skill(tmp_path):
    """A SKILL.md without a `factory: document` stamp is not the plugin's
    business — classified as untracked, not flagged as a problem."""
    (tmp_path / ".claude/skills/other").mkdir(parents=True)
    skill = tmp_path / ".claude/skills/other/SKILL.md"
    skill.write_text("---\nname: other\n---\n\n", encoding="utf-8")
    result = us.classify_artifact(
        "skill", skill, skill.read_text(encoding="utf-8"), tmp_path, INSTALLED,
    )
    assert result["classification"] == "untracked"


# --------------------------------------------------------------------------
# classification — config files
# --------------------------------------------------------------------------

def _write_root(repo, *, schema_line):
    root = repo / ".config/documents/root.md"
    root.parent.mkdir(parents=True, exist_ok=True)
    root.write_text(
        "# Document Root\n\n## Configuration\n- root-type: project\n"
        + (schema_line + "\n" if schema_line else ""),
        encoding="utf-8",
    )
    return root


def test_classify_config_current(tmp_path):
    root = _write_root(tmp_path, schema_line="- schema-version: 1")
    result = us.classify_artifact("config", root, root.read_text(encoding="utf-8"),
                                  tmp_path, INSTALLED)
    assert result["classification"] == "current"
    assert result["schema-version"] == 1


def test_classify_config_absent_version_is_v1(tmp_path):
    root = _write_root(tmp_path, schema_line="")
    result = us.classify_artifact("config", root, root.read_text(encoding="utf-8"),
                                  tmp_path, INSTALLED)
    assert result["classification"] == "current"
    assert result["schema-version"] == 1


def test_classify_config_migration_needed(tmp_path):
    root = _write_root(tmp_path, schema_line="- schema-version: 1")
    installed_v2 = dict(INSTALLED, **{"document-schema-version": 2})
    result = us.classify_artifact("config", root, root.read_text(encoding="utf-8"),
                                  tmp_path, installed_v2)
    assert result["classification"] == "migration-needed"


def test_classify_config_ahead(tmp_path):
    root = _write_root(tmp_path, schema_line="- schema-version: 3")
    result = us.classify_artifact("config", root, root.read_text(encoding="utf-8"),
                                  tmp_path, INSTALLED)
    assert result["classification"] == "ahead"


# --------------------------------------------------------------------------
# discovery + end-to-end scan
# --------------------------------------------------------------------------

def test_discover_walks_correct_dirs_and_skips_excluded(tmp_path):
    """Materialized artifacts live under `.claude/` and `.config/documents/`;
    `.cursor/`, `.github/`, `plugins/`, `.venv/` are never scanned."""
    _write_prd_artifacts(tmp_path)
    # Plant a decoy SKILL.md inside an excluded dir.
    (tmp_path / "plugins/document/skills/decoy").mkdir(parents=True)
    (tmp_path / "plugins/document/skills/decoy/SKILL.md").write_text(
        "---\nname: decoy\nfactory: document\n---\n", encoding="utf-8",
    )
    (tmp_path / ".cursor/skills/decoy").mkdir(parents=True)
    (tmp_path / ".cursor/skills/decoy/SKILL.md").write_text(
        "---\nname: decoy\nfactory: document\n---\n", encoding="utf-8",
    )

    artifacts = us.discover_artifacts(tmp_path)
    paths = [str(p.relative_to(tmp_path)) for _, p, _ in artifacts]
    assert ".claude/skills/prd/SKILL.md" in paths
    assert all("plugins/" not in p for p in paths)
    assert all(".cursor/" not in p for p in paths)


def test_scan_emits_available_for_unmaterialized_templates(tmp_path):
    """A plugin template with no materialized form in the repo is classified
    `available` so /document:upgrade can install it in the same pass as
    stale/migration work — without a separate `materialize` subcommand."""
    result = us.scan(tmp_path, PLUGIN_ROOT)
    available = {a["template"] for a in result["artifacts"]
                 if a.get("classification") == "available"}
    assert {"document-events", "document-enrich",
            "document-lint", "document-verify-inferred"} <= available


def test_scan_drops_available_once_materialized(tmp_path):
    """Once materialized, the template stops appearing in `available` — the
    materialized form is now classified on its own merits (current / stale)."""
    skill_dir = tmp_path / ".claude/skills/document-events"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: document-events\n---\n", encoding="utf-8",
    )
    available = {
        a["template"] for a in us.scan(tmp_path, PLUGIN_ROOT)["artifacts"]
        if a.get("classification") == "available"
    }
    assert "document-events" not in available
    # Other templates remain available.
    assert "document-enrich" in available


def test_scan_end_to_end(tmp_path):
    """scan() yields a classification per discovered artifact, against the
    installed plugin's real versions (this plugin)."""
    _write_prd_artifacts(tmp_path)
    _write_root(tmp_path, schema_line="- schema-version: 1")
    result = us.scan(tmp_path, PLUGIN_ROOT)
    assert "installed" in result
    assert result["installed"]["factory-version"]  # populated from real plugin
    paths = {a["path"]: a for a in result["artifacts"]}
    assert ".claude/skills/prd/SKILL.md" in paths
    assert ".config/documents/types/prd.md" in paths
    assert ".config/documents/root.md" in paths


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_version():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "upgrade-scan.py" in result.stdout


def test_cli_emits_json(tmp_path):
    _write_prd_artifacts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "installed" in payload and "artifacts" in payload


# --------------------------------------------------------------------------
# version comparison — regression tests for the padding fix
# --------------------------------------------------------------------------

def test_cmp_version_pads_shorter_tuple():
    """Mixed-length version components must compare correctly so a stamp
    written with one component count never falsely flags ahead/stale
    against an installed plugin using a different count."""
    assert us._cmp_version("0.9", "0.9.0") == 0
    assert us._cmp_version("1.4", "1.4.0") == 0
    assert us._cmp_version("0.9.0", "0.10.0") == -1
    assert us._cmp_version("1.10", "1.9") == 1
    assert us._cmp_version("0.9", "0.9.1") == -1
    assert us._cmp_version("garbage", "0.1.0") is None


# --------------------------------------------------------------------------
# Tier-2 source-orphan check
# --------------------------------------------------------------------------

def test_classify_tier2_orphan_when_source_missing(tmp_path):
    """A Tier-2-materialized skill whose source template no longer exists
    in the installed plugin is an orphan — the plugin removed it (e.g.
    document-render after Phase 2)."""
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    # plugin_root exists but does not contain the source the stamp references.

    skill_dir = tmp_path / ".claude/skills/document-events"
    skill_dir.mkdir(parents=True)
    skill = skill_dir / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: document-events\n"
        "factory: document\n"
        'factory-version: "0.8.0"\n'
        "generated-by: document-upgrade\n"
        'generator-version: "1.4"\n'
        'source: "skills/document-events/SKILL.md"\n'
        'materialized: "2026-05-22"\n'
        "tier: 2-materialized\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    result = us.classify_artifact(
        "skill", skill, skill.read_text(encoding="utf-8"),
        tmp_path, INSTALLED, plugin_root=plugin_root,
    )
    assert result["classification"] == "orphan"
    assert any("source missing" in r for r in result["reasons"])


def test_classify_tier2_not_orphan_when_source_exists(tmp_path):
    """The mirror of the above — source present → not orphan."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "skills/document-events").mkdir(parents=True)
    (plugin_root / "skills/document-events/SKILL.md").write_text("source", encoding="utf-8")

    skill_dir = tmp_path / ".claude/skills/document-events"
    skill_dir.mkdir(parents=True)
    skill = skill_dir / "SKILL.md"
    skill.write_text(
        "---\nname: document-events\nfactory: document\n"
        'factory-version: "0.8.0"\ngenerated-by: document-upgrade\n'
        'generator-version: "1.4"\nsource: "skills/document-events/SKILL.md"\n'
        'materialized: "2026-05-22"\ntier: 2-materialized\n---\n',
        encoding="utf-8",
    )
    result = us.classify_artifact(
        "skill", skill, skill.read_text(encoding="utf-8"),
        tmp_path, INSTALLED, plugin_root=plugin_root,
    )
    assert result["classification"] != "orphan"


# --------------------------------------------------------------------------
# scan_targets — Phase 1 / multi-harness
# --------------------------------------------------------------------------

def test_scan_targets_missing_config_uses_defaults(tmp_path):
    """Fresh repo: no .config/documents/rulesync.jsonc → defaults
    (cursor + codexcli), no detected outputs, no error."""
    result = us.scan_targets(tmp_path)
    assert result["config_exists"] is False
    assert result["config_error"] is None
    assert result["configured"] == ["codexcli", "cursor"]
    assert result["detected"] == []
    assert result["unconfigured"] == []


def test_scan_targets_reads_existing_config(tmp_path):
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": '
        '{"cursor": ["skills"], "copilot": ["skills"]}}\n'
    )
    result = us.scan_targets(tmp_path)
    assert result["config_exists"] is True
    assert result["configured"] == ["copilot", "cursor"]


def test_scan_targets_detects_unconfigured_output(tmp_path):
    """`.github/skills/` is present on disk but `copilot` isn't in the
    config → must appear in `unconfigured` so /document:upgrade can
    prompt."""
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": {"cursor": ["skills"]}}\n'
    )
    (tmp_path / ".github/skills/document-lint").mkdir(parents=True)
    (tmp_path / ".github/skills/document-lint/SKILL.md").write_text("body\n")
    result = us.scan_targets(tmp_path)
    assert "copilot" in result["detected"]
    assert "copilot" in result["unconfigured"]
    assert "cursor" not in result["unconfigured"]


def test_scan_targets_configured_outputs_not_unconfigured(tmp_path):
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": '
        '{"cursor": ["skills"], "codexcli": ["skills"]}}\n'
    )
    (tmp_path / ".cursor/skills").mkdir(parents=True)
    (tmp_path / ".codex").mkdir(parents=True)
    result = us.scan_targets(tmp_path)
    assert result["detected"] == ["codexcli", "cursor"]
    assert result["unconfigured"] == []


def test_scan_targets_recognises_all_known_target_dirs(tmp_path):
    """Every entry in KNOWN_TARGET_DIRS must be detectable — guards
    against accidentally removing one from the map."""
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": {"cursor": ["skills"]}}\n'
    )
    for name, rel in us.KNOWN_TARGET_DIRS.items():
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    result = us.scan_targets(tmp_path)
    assert set(result["detected"]) == set(us.KNOWN_TARGET_DIRS.keys())


def test_scan_targets_malformed_config_surfaces_error(tmp_path):
    """A malformed rulesync.jsonc must not crash the scan — surface
    the error and proceed with defaults so the rest of /document:upgrade
    can still run."""
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text('{not json')
    result = us.scan_targets(tmp_path)
    assert result["config_error"] is not None
    assert "JSONC" in result["config_error"] or "invalid" in result["config_error"]
    # falls back to defaults
    assert result["configured"] == ["codexcli", "cursor"]


def test_scan_includes_targets_section(tmp_path):
    """End-to-end: scan(repo, plugin) output dict has a top-level
    `targets` section."""
    result = us.scan(tmp_path, PLUGIN_ROOT)
    assert "targets" in result
    assert "configured" in result["targets"]
