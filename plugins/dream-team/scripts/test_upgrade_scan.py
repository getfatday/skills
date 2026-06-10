"""Layer 1 — unit tests for upgrade-scan.py.

Exercises version comparison, provenance parsing, schema-version parsing,
artifact discovery, and the classification matrix (current / stale / orphan /
ahead / detached / untracked / malformed / migration-needed). Deterministic.
"""
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
# Dashes in module names: load via importlib instead of `import upgrade-scan`.
import importlib.util as _util
_spec = _util.spec_from_file_location("upgrade_scan", _HERE / "upgrade-scan.py")
upgrade_scan = _util.module_from_spec(_spec)
_spec.loader.exec_module(upgrade_scan)

PLUGIN_ROOT = _HERE.parent

INSTALLED_STUB = {
    "factory-version": "0.5.2",
    "generator-version": "0.1",
    "dream-team-schema-version": 1,
}


# --------------------------------------------------------------------------
# version comparison
# --------------------------------------------------------------------------

def test_parse_version_basic():
    assert upgrade_scan._parse_version("0.5.0") == (0, 5, 0)
    assert upgrade_scan._parse_version("1.4") == (1, 4)


def test_parse_version_bad_input():
    assert upgrade_scan._parse_version(None) is None
    assert upgrade_scan._parse_version("not-a-version") is None
    assert upgrade_scan._parse_version("1.x.0") is None


def test_cmp_version_equal_after_padding():
    assert upgrade_scan._cmp_version("0.9", "0.9.0") == 0
    assert upgrade_scan._cmp_version("0.9.0", "0.9") == 0


def test_cmp_version_less_greater():
    assert upgrade_scan._cmp_version("0.5.1", "0.5.2") == -1
    assert upgrade_scan._cmp_version("0.6.0", "0.5.2") == 1
    assert upgrade_scan._cmp_version("0.5.1", "0.5.1") == 0


def test_cmp_version_unknown():
    assert upgrade_scan._cmp_version("0.5", "garbage") is None


# --------------------------------------------------------------------------
# frontmatter and provenance parsing
# --------------------------------------------------------------------------

def test_parse_frontmatter_basic():
    text = "---\nname: kent-beck\ntier: 3\n---\nbody\n"
    fm = upgrade_scan.parse_frontmatter(text)
    assert fm["name"] == "kent-beck"
    assert fm["tier"] == "3"


def test_parse_frontmatter_quoted_values():
    text = "---\nname: 'foo'\ndescription: \"bar\"\n---\n"
    fm = upgrade_scan.parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["description"] == "bar"


def test_parse_frontmatter_empty_when_missing():
    assert upgrade_scan.parse_frontmatter("no frontmatter here") == {}
    assert upgrade_scan.parse_frontmatter("") == {}


def test_parse_provenance_filters_non_dream_team():
    text = (
        "---\nfactory: document\nfactory-version: 1.0\n"
        "generated-by: x\ngenerator-version: 1\nsource: x\n"
        "materialized: x\ntier: 3\n---\n"
    )
    assert upgrade_scan.parse_provenance(text) == {}


def test_parse_provenance_accepts_dream_team():
    text = (
        "---\nfactory: dream-team\nfactory-version: '0.5.2'\n"
        "generated-by: 'team-member-recruit'\ngenerator-version: '0.1'\n"
        "source: 's'\nmaterialized: 'm'\ntier: 3\n---\n"
    )
    stamp = upgrade_scan.parse_provenance(text)
    assert stamp["factory"] == "dream-team"
    assert stamp["factory-version"] == "0.5.2"


# --------------------------------------------------------------------------
# schema-version parsing
# --------------------------------------------------------------------------

def test_parse_schema_version_frontmatter():
    text = "---\nschema-version: 1\n---\n"
    assert upgrade_scan.parse_config_schema_version(text) == 1


def test_parse_schema_version_body_form():
    text = (
        "# Team Root\n\n## Configuration\n"
        "- schema-version: 2\n"
    )
    assert upgrade_scan.parse_config_schema_version(text) == 2


def test_parse_schema_version_absent_returns_none():
    assert upgrade_scan.parse_config_schema_version("# blah\n") is None


# --------------------------------------------------------------------------
# classification — config files
# --------------------------------------------------------------------------

def test_classify_config_current_when_versions_match(tmp_path):
    root = tmp_path / ".config/team/root.md"
    root.parent.mkdir(parents=True)
    root.write_text("---\nschema-version: 1\n---\n# Team Root\n")
    result = upgrade_scan.classify_artifact(
        "config-root", root, root.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "current"
    assert result["schema-version"] == 1


def test_classify_config_absent_schema_version_treated_as_one(tmp_path):
    root = tmp_path / ".config/team/root.md"
    root.parent.mkdir(parents=True)
    root.write_text("# Team Root\n")
    result = upgrade_scan.classify_artifact(
        "config-root", root, root.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "current"
    assert result["schema-version"] == 1


def test_classify_config_migration_needed(tmp_path):
    root = tmp_path / ".config/team/root.md"
    root.parent.mkdir(parents=True)
    root.write_text("---\nschema-version: 1\n---\n")
    installed = dict(INSTALLED_STUB, **{"dream-team-schema-version": 2})
    result = upgrade_scan.classify_artifact(
        "config-root", root, root.read_text(), tmp_path, installed,
    )
    assert result["classification"] == "migration-needed"


def test_classify_config_ahead(tmp_path):
    root = tmp_path / ".config/team/root.md"
    root.parent.mkdir(parents=True)
    root.write_text("---\nschema-version: 99\n---\n")
    result = upgrade_scan.classify_artifact(
        "config-root", root, root.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "ahead"


# --------------------------------------------------------------------------
# classification — provenance-stamped artifacts
# --------------------------------------------------------------------------

def _make_skill(tmp_path, slug, *, factory_version, blueprint_content="kb",
                with_mirrors=True):
    """Helper: write a blueprint + a materialized skill with provenance.

    `with_mirrors=True` (default) also lays down the Cursor and Copilot
    mirrors so the artifact classifies as `current` post-Phase 5. Set False
    in tests that exercise the `mirror-missing` reason code."""
    blueprint = tmp_path / ".config/team/team-members" / f"{slug}.md"
    blueprint.parent.mkdir(parents=True, exist_ok=True)
    blueprint.write_text(blueprint_content)
    h = upgrade_scan._sha256(blueprint_content)
    skill = tmp_path / ".claude/skills" / slug / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {slug}\nfactory: dream-team\n"
        f"factory-version: '{factory_version}'\n"
        f"generated-by: 'team-member-recruit'\ngenerator-version: '0.1'\n"
        f"source: 'templates/team-members/{slug}/skills/{slug}/SKILL.md'\n"
        f"materialized: '2026-06-08'\ntier: 3\n"
        f"blueprint: '.config/team/team-members/{slug}.md'\n"
        f"blueprint-hash: '{h}'\n---\nbody\n"
    )
    if with_mirrors:
        for mirror in [
            tmp_path / ".cursor/skills" / slug / "SKILL.md",
            tmp_path / ".github/skills" / slug / "SKILL.md",
        ]:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_text(
                f"---\nname: {slug}\ndescription: stub\n---\nbody\n"
            )
    return skill


def test_classify_skill_current(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "current"
    assert result["reasons"] == []


def test_classify_skill_stale_factory_version(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.0")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert any("factory-version" in r for r in result["reasons"])


def test_classify_skill_stale_blueprint_edited(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    # User edits blueprint after materialization — hash no longer matches.
    blueprint = tmp_path / ".config/team/team-members/kent-beck.md"
    blueprint.write_text("kb-edited-by-user")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert any("blueprint-hash drift" in r for r in result["reasons"])


def test_classify_skill_orphan_blueprint_deleted(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    (tmp_path / ".config/team/team-members/kent-beck.md").unlink()
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "orphan"


def test_classify_skill_ahead(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="9.9.9")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "ahead"


def test_classify_skill_untracked(tmp_path):
    skill = tmp_path / ".claude/skills/hand-written/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: hand-written\n---\nNo provenance.\n")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "untracked"


def test_classify_skill_detached(tmp_path):
    skill = tmp_path / ".claude/skills/kent-beck/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: kent-beck\nfactory: dream-team\n"
        "factory-version: '0.5.2'\ngenerated-by: x\ngenerator-version: '0.1'\n"
        "source: 's'\nmaterialized: 'm'\ntier: 3\n"
        "provenance: detached\n---\n"
    )
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "detached"


def test_classify_skill_emits_slug_from_path(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["slug"] == "kent-beck"


def test_classify_team_skill_keeps_team_prefix_in_slug(tmp_path):
    # Team skills materialize at .claude/skills/team-engineering/SKILL.md;
    # the slug field should be 'team-engineering' (not 'engineering').
    skill_dir = tmp_path / ".claude/skills/team-engineering"
    skill_dir.mkdir(parents=True)
    (tmp_path / ".config/team/teams").mkdir(parents=True)
    blueprint = tmp_path / ".config/team/teams/engineering.md"
    blueprint.write_text("eng")
    skill = skill_dir / "SKILL.md"
    skill.write_text(
        "---\nname: team-engineering\nfactory: dream-team\n"
        "factory-version: '0.5.2'\ngenerated-by: x\ngenerator-version: '0.1'\n"
        "source: 's'\nmaterialized: 'm'\ntier: 3\n---\n"
    )
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["slug"] == "team-engineering"


def test_classify_config_member_slug_is_filename_stem(tmp_path):
    config = tmp_path / ".config/team/team-members/kent-beck.md"
    config.parent.mkdir(parents=True)
    config.write_text("---\nschema-version: 1\n---\n")
    result = upgrade_scan.classify_artifact(
        "config-member", config, config.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["slug"] == "kent-beck"


def test_classify_skill_reason_codes_blueprint_drift(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    (tmp_path / ".config/team/team-members/kent-beck.md").write_text("edited")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert "blueprint-hash-drift" in result["reason_codes"]
    assert "factory-version-drift" not in result["reason_codes"]


def test_classify_skill_reason_codes_factory_drift(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.0")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert "factory-version-drift" in result["reason_codes"]


def test_classify_skill_reason_codes_orphan(tmp_path):
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    (tmp_path / ".config/team/team-members/kent-beck.md").unlink()
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["reason_codes"] == ["blueprint-missing"]


def test_classify_untracked_has_reason_code(tmp_path):
    skill = tmp_path / ".claude/skills/hand-written/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: hand-written\n---\nNo provenance.\n")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["reason_codes"] == ["no-provenance-stamp"]


def test_classify_skill_flags_missing_cursor_mirror(tmp_path):
    """Phase 5: when the Claude skill exists and is current but the Cursor
    mirror is missing, scanner should mark stale with reason_code
    mirror-missing so team-update re-materializes the harness mirrors."""
    skill = _make_skill(
        tmp_path, "kent-beck", factory_version="0.5.2", with_mirrors=False,
    )
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert "mirror-missing" in result["reason_codes"]
    assert any(".cursor/skills/kent-beck/SKILL.md" in r for r in result["reasons"])
    assert any(".github/skills/kent-beck/SKILL.md" in r for r in result["reasons"])


def test_classify_skill_current_when_mirrors_present(tmp_path):
    """Cursor + GitHub mirrors present alongside the Claude skill → current."""
    skill = _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "current"
    assert result["reason_codes"] == []


def test_classify_skill_missing_only_one_mirror(tmp_path):
    """A single missing mirror still triggers stale."""
    skill = _make_skill(
        tmp_path, "kent-beck", factory_version="0.5.2", with_mirrors=False,
    )
    p = tmp_path / ".cursor/skills/kent-beck/SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nname: kent-beck\ndescription: stub\n---\nBody")
    # GitHub mirror still missing.
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "stale"
    assert "mirror-missing" in result["reason_codes"]
    assert any(".github/skills/kent-beck/SKILL.md" in r for r in result["reasons"])
    assert not any(".cursor/skills/kent-beck/SKILL.md" in r for r in result["reasons"])


def test_classify_skill_malformed_missing_fields(tmp_path):
    skill = tmp_path / ".claude/skills/x/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nfactory: dream-team\nfactory-version: '0.5.2'\n---\n"
    )
    result = upgrade_scan.classify_artifact(
        "skill", skill, skill.read_text(), tmp_path, INSTALLED_STUB,
    )
    assert result["classification"] == "malformed"
    assert "missing stamp fields" in result["reasons"][0]


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

def test_discover_finds_skills_commands_agents_configs(tmp_path):
    # Set up a mini consumer tree.
    _make_skill(tmp_path, "kent-beck", factory_version="0.5.2")
    (tmp_path / ".claude/commands/consult.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude/commands/consult.md").write_text(
        "---\nfactory: dream-team\n---\n"
    )
    (tmp_path / ".claude/agents/orchestrator.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude/agents/orchestrator.md").write_text(
        "---\nfactory: dream-team\n---\n"
    )
    (tmp_path / ".config/team/teams").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".config/team/teams/engineering.md").write_text(
        "---\nschema-version: 1\n---\n"
    )
    artifacts = upgrade_scan.discover_artifacts(tmp_path)
    kinds = sorted({k for k, _, _ in artifacts})
    assert "skill" in kinds
    assert "command" in kinds
    assert "agent" in kinds
    assert "config-root" not in kinds  # not created above
    assert "config-member" in kinds
    assert "config-team" in kinds


def test_discover_skips_excluded_dirs(tmp_path):
    (tmp_path / ".git/skills/x").mkdir(parents=True)
    (tmp_path / ".git/skills/x/SKILL.md").write_text("---\nfactory: dream-team\n---\n")
    (tmp_path / "plugins/foo/skills/x").mkdir(parents=True)
    (tmp_path / "plugins/foo/skills/x/SKILL.md").write_text(
        "---\nfactory: dream-team\n---\n"
    )
    artifacts = upgrade_scan.discover_artifacts(tmp_path)
    assert artifacts == []


# --------------------------------------------------------------------------
# scan_repo end-to-end
# --------------------------------------------------------------------------

def test_scan_repo_returns_installed_counts_and_artifacts(tmp_path):
    _make_skill(tmp_path, "kent-beck", factory_version="0.5.0")  # stale
    _make_skill(tmp_path, "marty-cagan",
                factory_version=PLUGIN_ROOT.joinpath(
                    ".claude-plugin/plugin.json"
                ).read_text().split('"version":')[1].split('"')[1])  # current
    report = upgrade_scan.scan_repo(tmp_path, PLUGIN_ROOT)
    assert "installed" in report
    assert "factory-version" in report["installed"]
    assert "counts" in report
    assert "artifacts" in report
    classifications = {a["classification"] for a in report["artifacts"]}
    # Two skills, classifications include at least 'stale' and 'current'.
    assert "stale" in classifications
    assert "current" in classifications


# --------------------------------------------------------------------------
# read_installed_versions
# --------------------------------------------------------------------------

def test_read_installed_versions_from_real_plugin():
    versions = upgrade_scan.read_installed_versions(PLUGIN_ROOT)
    assert versions["factory-version"]  # non-empty
    assert versions["dream-team-schema-version"] == 1
