"""Layer 1 — unit tests for materialize.py.

Exercises the materializer end-to-end against a temporary consumer repo:
provenance stamping, <extends> rewriting, team-assemble + orchestrator +
entry commands bootstrap, per-member and per-team artifact emission.
Deterministic (no calls to today() — caller passes the date in).
"""
import hashlib
import json
import pathlib
import sys

# Make the script directory importable so we can import materialize as a module.
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import materialize  # noqa: E402

PLUGIN_ROOT = _HERE.parent
TODAY = "2026-06-08"
FV = "0.4.5"
GV = "0.1"


# --------------------------------------------------------------------------
# inject_provenance_frontmatter
# --------------------------------------------------------------------------

def test_inject_provenance_adds_missing_fields():
    template = "---\nname: kent-beck\ntier: 3\n---\nbody\n"
    out = materialize.inject_provenance_frontmatter(
        template, factory_version=FV, generator_version=GV,
        source="templates/team-members/kent-beck/skills/kent-beck/SKILL.md",
        today=TODAY, blueprint_path=".config/team/team-members/kent-beck.md",
        blueprint_hash="abc123",
    )
    assert "factory: 'dream-team'" in out
    assert f"factory-version: '{FV}'" in out
    assert "generated-by: 'team-member-recruit'" in out
    assert "source: 'templates/team-members/kent-beck/skills/kent-beck/SKILL.md'" in out
    assert f"materialized: '{TODAY}'" in out
    assert "blueprint: '.config/team/team-members/kent-beck.md'" in out
    assert "blueprint-hash: 'abc123'" in out
    # Existing fields preserved.
    assert "name: kent-beck" in out
    assert "tier: 3" in out
    # Body untouched.
    assert "body" in out


def test_inject_provenance_preserves_tier():
    """tier: is template-owned and must never be overwritten."""
    template = "---\nname: x\ntier: 2-materialized\n---\n"
    out = materialize.inject_provenance_frontmatter(
        template, factory_version=FV, generator_version=GV,
        source="x", today=TODAY,
    )
    # tier appears exactly once.
    assert out.count("tier:") == 1
    assert "tier: 2-materialized" in out


def test_inject_provenance_idempotent():
    """Re-running the materializer on its own output produces no drift."""
    template = "---\nname: x\ntier: 3\n---\nbody\n"
    once = materialize.inject_provenance_frontmatter(
        template, factory_version=FV, generator_version=GV,
        source="x", today=TODAY,
    )
    twice = materialize.inject_provenance_frontmatter(
        once, factory_version=FV, generator_version=GV,
        source="x", today=TODAY,
    )
    assert once == twice


def test_inject_provenance_rejects_no_frontmatter():
    import pytest
    with pytest.raises(ValueError, match="leading frontmatter"):
        materialize.inject_provenance_frontmatter(
            "no frontmatter here\n",
            factory_version=FV, generator_version=GV, source="x", today=TODAY,
        )


# --------------------------------------------------------------------------
# rewrite_extends
# --------------------------------------------------------------------------

def test_rewrite_extends_strips_skills_segment():
    text = "<extends>\n- `team-engineering/skills/engineering/SKILL.md`\n</extends>"
    out = materialize.rewrite_extends(text)
    assert "team-engineering/SKILL.md" in out
    assert "team-engineering/skills/" not in out


def test_rewrite_extends_handles_multiple_paths():
    text = (
        "<extends>\n"
        "- `team-engineering/skills/engineering/SKILL.md`\n"
        "- `team-product/skills/product/SKILL.md`\n"
        "</extends>\n"
    )
    out = materialize.rewrite_extends(text)
    assert "team-engineering/SKILL.md" in out
    assert "team-product/SKILL.md" in out


def test_rewrite_extends_leaves_unrelated_paths_alone():
    text = "see `team-engineering/SKILL.md` and `.claude/skills/x/SKILL.md`"
    out = materialize.rewrite_extends(text)
    assert out == text  # nothing to rewrite


# --------------------------------------------------------------------------
# materialize_team_assemble — bootstrap of the workflow engine
# --------------------------------------------------------------------------

def test_materialize_team_assemble_emits_skill_and_patterns(tmp_path):
    written = materialize.materialize_team_assemble(
        PLUGIN_ROOT, tmp_path, dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    skill_md = tmp_path / ".claude/skills/team-assemble/SKILL.md"
    assert skill_md.is_file()
    skill_text = skill_md.read_text(encoding="utf-8")
    # Provenance stamped.
    for field in ("factory: 'dream-team'", f"factory-version: '{FV}'",
                  "generated-by: 'team-update'", "tier: 2-materialized"):
        assert field in skill_text

    # Patterns subdirectory populated.
    patterns_dir = tmp_path / ".claude/skills/team-assemble/patterns"
    assert patterns_dir.is_dir()
    pattern_files = sorted(patterns_dir.glob("*.md"))
    assert len(pattern_files) >= 10, f"only {len(pattern_files)} patterns materialized"
    # router.md and primitives.md must be there — orchestrator reads them.
    assert (patterns_dir / "router.md").is_file()
    assert (patterns_dir / "primitives.md").is_file()

    # Written list reports relative paths.
    assert any(p.endswith("team-assemble/SKILL.md") for p in written)


def test_materialize_team_assemble_dry_run_writes_nothing(tmp_path):
    written = materialize.materialize_team_assemble(
        PLUGIN_ROOT, tmp_path, dry_run=True, today=TODAY, fv=FV, gv=GV,
    )
    assert written  # dry-run still reports what it would write
    assert not (tmp_path / ".claude").exists()


# --------------------------------------------------------------------------
# materialize_orchestrator
# --------------------------------------------------------------------------

def test_materialize_orchestrator_lands_at_claude_agents(tmp_path):
    written = materialize.materialize_orchestrator(
        PLUGIN_ROOT, tmp_path, dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    orch = tmp_path / ".claude/agents/orchestrator.md"
    assert orch.is_file()
    text = orch.read_text(encoding="utf-8")
    assert "factory: 'dream-team'" in text
    assert "tier: 2-materialized" in text
    assert any(p.endswith("agents/orchestrator.md") for p in written)


# --------------------------------------------------------------------------
# materialize_entry_commands
# --------------------------------------------------------------------------

def test_materialize_entry_commands_emits_four_verbs(tmp_path):
    written = materialize.materialize_entry_commands(
        PLUGIN_ROOT, tmp_path, dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    for verb in ("consult", "coach", "plan", "review"):
        cmd = tmp_path / ".claude/commands" / f"{verb}.md"
        assert cmd.is_file(), f"missing materialized {verb} command"
        text = cmd.read_text(encoding="utf-8")
        assert "factory: 'dream-team'" in text
        assert "tier: 2-materialized" in text
    assert sum(p.endswith(".md") for p in written) == 4


# --------------------------------------------------------------------------
# materialize_team_member — Tier 3 with blueprint + hash
# --------------------------------------------------------------------------

def test_materialize_team_member_kent_beck(tmp_path):
    written = materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    # 1. Blueprint copied verbatim into .config/team/team-members/.
    blueprint = tmp_path / ".config/team/team-members/kent-beck.md"
    assert blueprint.is_file()
    plugin_blueprint = (
        PLUGIN_ROOT / "templates/team-members/kent-beck/TEAM-MEMBER.md"
    )
    assert blueprint.read_text(encoding="utf-8") == plugin_blueprint.read_text(
        encoding="utf-8"
    )

    # 2. Persona skill at .claude/skills/kent-beck/SKILL.md, stamped.
    skill = tmp_path / ".claude/skills/kent-beck/SKILL.md"
    assert skill.is_file()
    skill_text = skill.read_text(encoding="utf-8")
    assert "factory: 'dream-team'" in skill_text
    assert "generated-by: 'team-member-recruit'" in skill_text
    assert "blueprint: '.config/team/team-members/kent-beck.md'" in skill_text
    assert "blueprint-hash:" in skill_text
    # <extends> rewritten — no plugin-tree path.
    assert "team-engineering/skills/engineering/SKILL.md" not in skill_text
    assert "team-engineering/SKILL.md" in skill_text

    # 3. References copied.
    for ref in ("principles.md", "anti-patterns.md", "vocabulary.md"):
        assert (tmp_path / ".claude/skills/kent-beck/references" / ref).is_file()

    assert any(p.endswith("kent-beck.md") for p in written)


def test_materialize_team_member_keep_blueprint_preserves_user_edits(tmp_path):
    """When --keep-blueprint is set and an on-disk blueprint exists, the
    materializer must NOT overwrite it with the template — and it must hash
    the on-disk blueprint when stamping the persona skill. This is the
    correctness contract for team-member-update's re-materialization step."""
    # First materialization seeds the blueprint from the template.
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    blueprint = tmp_path / ".config/team/team-members/kent-beck.md"
    edited = (
        blueprint.read_text(encoding="utf-8")
        + "\n\n<recent-material>Tidy First — 2023, Pragmatic Bookshelf.</recent-material>\n"
    )
    blueprint.write_text(edited, encoding="utf-8")
    edited_hash = hashlib.sha256(edited.encode("utf-8")).hexdigest()

    # Second materialization in keep-blueprint mode.
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        keep_blueprint=True,
    )

    # User edit survived.
    assert blueprint.read_text(encoding="utf-8") == edited
    # Persona skill's blueprint-hash stamp matches the EDITED text, not the
    # template.
    skill_text = (tmp_path / ".claude/skills/kent-beck/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert f"blueprint-hash: '{edited_hash}'" in skill_text


def test_materialize_team_member_keep_blueprint_no_disk_blueprint_falls_back(tmp_path):
    """If --keep-blueprint is set but there's no on-disk blueprint, the
    materializer behaves like a normal first install (writes from template)
    rather than failing."""
    written = materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        keep_blueprint=True,
    )
    blueprint = tmp_path / ".config/team/team-members/kent-beck.md"
    assert blueprint.is_file()
    plugin_blueprint = (
        PLUGIN_ROOT / "templates/team-members/kent-beck/TEAM-MEMBER.md"
    )
    assert blueprint.read_text(encoding="utf-8") == plugin_blueprint.read_text(
        encoding="utf-8"
    )
    assert any(p.endswith("kent-beck.md") for p in written)


# --------------------------------------------------------------------------
# materialize_team — Tier 3 team layer with team- prefix
# --------------------------------------------------------------------------

def test_materialize_team_engineering(tmp_path):
    written = materialize.materialize_team(
        PLUGIN_ROOT, tmp_path, "engineering",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    blueprint = tmp_path / ".config/team/teams/engineering.md"
    assert blueprint.is_file()
    skill = tmp_path / ".claude/skills/team-engineering/SKILL.md"
    assert skill.is_file()
    skill_text = skill.read_text(encoding="utf-8")
    # The skill name was rewritten to team-engineering (matches new directory).
    assert "name: team-engineering" in skill_text
    assert "factory: 'dream-team'" in skill_text


# --------------------------------------------------------------------------
# Phase 5 — multi-harness fanout
# --------------------------------------------------------------------------

def test_materialize_team_member_fans_out_to_all_targets(tmp_path):
    """A single --member kent-beck --targets all run must emit the same
    artifact into Claude, Cursor, and Copilot trees."""
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("claude", "cursor", "copilot"),
    )

    # Skill present in all three trees.
    for path in [
        ".claude/skills/kent-beck/SKILL.md",
        ".cursor/skills/kent-beck/SKILL.md",
        ".github/skills/kent-beck/SKILL.md",
    ]:
        assert (tmp_path / path).is_file(), f"{path} not materialized"

    # references/ mirrored byte-identical.
    claude_ref = (tmp_path / ".claude/skills/kent-beck/references/principles.md").read_text()
    cursor_ref = (tmp_path / ".cursor/skills/kent-beck/references/principles.md").read_text()
    copilot_ref = (tmp_path / ".github/skills/kent-beck/references/principles.md").read_text()
    assert claude_ref == cursor_ref == copilot_ref


def test_materialize_cursor_skill_strips_provenance_frontmatter(tmp_path):
    """The Cursor mirror must NOT carry the full provenance stamp; only
    name + description. Cursor's frontmatter parser rejects unknown fields."""
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("cursor",),
    )
    text = (tmp_path / ".cursor/skills/kent-beck/SKILL.md").read_text()
    # Frontmatter only keeps name + description.
    assert "factory-version:" not in text
    assert "blueprint-hash:" not in text
    assert "generated-by:" not in text
    assert "tier:" not in text
    assert "name:" in text
    assert "description:" in text


def test_materialize_copilot_command_uses_prompt_md_extension(tmp_path):
    """Copilot expects entry verbs at .github/prompts/<verb>.prompt.md, not
    .md or in a skills/ subdir."""
    materialize.materialize_entry_commands(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("copilot",),
    )
    for verb in ("consult", "coach", "plan", "review"):
        assert (tmp_path / f".github/prompts/{verb}.prompt.md").is_file()
        # Must NOT also write to .claude/ in copilot-only mode.
        assert not (tmp_path / f".claude/commands/{verb}.md").exists()


def test_materialize_orchestrator_only_emitted_for_claude(tmp_path):
    """Cursor/Copilot have no agents; the orchestrator must be a no-op for
    those targets."""
    materialize.materialize_orchestrator(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("cursor", "copilot"),
    )
    assert not (tmp_path / ".claude/agents/orchestrator.md").exists()

    materialize.materialize_orchestrator(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("claude",),
    )
    assert (tmp_path / ".claude/agents/orchestrator.md").is_file()


def test_materialize_defaults_to_claude_only_for_back_compat(tmp_path):
    """When `targets=` is omitted, behave as the pre-Phase-5 materializer did
    (Claude only) so existing callers / tests don't break."""
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    assert (tmp_path / ".claude/skills/kent-beck/SKILL.md").is_file()
    assert not (tmp_path / ".cursor/skills/kent-beck/SKILL.md").exists()
    assert not (tmp_path / ".github/skills/kent-beck/SKILL.md").exists()


def test_materialize_cursor_artifact_has_no_plugin_root_literal(tmp_path):
    """Self-sufficiency rule: mirrors must not leak plugin-tree references."""
    materialize.materialize_team_member(
        PLUGIN_ROOT, tmp_path, "kent-beck",
        dry_run=False, today=TODAY, fv=FV, gv=GV,
        targets=("cursor", "copilot"),
    )
    for path in [
        ".cursor/skills/kent-beck/SKILL.md",
        ".github/skills/kent-beck/SKILL.md",
    ]:
        text = (tmp_path / path).read_text()
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
        assert "plugins/dream-team" not in text


# --------------------------------------------------------------------------
# Phase 6 — githooks materialization
# --------------------------------------------------------------------------

def test_materialize_githooks_writes_pre_commit_entry(tmp_path):
    written = materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    pre_commit = tmp_path / ".githooks/pre-commit"
    assert pre_commit.is_file()
    # Executable bit.
    import stat
    assert pre_commit.stat().st_mode & stat.S_IXUSR
    # The entry mentions the bypass clause so users have a paper trail.
    text = pre_commit.read_text(encoding="utf-8")
    assert "--no-verify" in text
    assert "check-blueprint-staged.py" in text
    assert ".githooks/pre-commit" in written


def test_materialize_githooks_writes_validator_and_checker(tmp_path):
    materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    assert (tmp_path / ".githooks/lib/team_member_validator.py").is_file()
    assert (tmp_path / ".githooks/lib/check-blueprint-staged.py").is_file()


def test_materialize_githooks_is_idempotent(tmp_path):
    """Running --githooks twice should overwrite without growing the
    output."""
    first = materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    second = materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    assert first == second


def test_materialize_githooks_dry_run_writes_nothing(tmp_path):
    materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=True, today=TODAY, fv=FV, gv=GV,
    )
    assert not (tmp_path / ".githooks").exists()


def test_materialize_githooks_refuses_to_clobber_foreign_pre_commit(tmp_path):
    """A consumer with their own pre-commit (lint chain, etc.) shouldn't
    silently lose it on the next materialize. The materializer refuses."""
    (tmp_path / ".githooks").mkdir()
    existing = tmp_path / ".githooks/pre-commit"
    existing.write_text("#!/bin/bash\necho 'my lint chain'\n")

    import pytest
    with pytest.raises(FileExistsError, match="already exists"):
        materialize.materialize_githooks(
            PLUGIN_ROOT, tmp_path,
            dry_run=False, today=TODAY, fv=FV, gv=GV,
        )
    # The existing file is untouched.
    assert "my lint chain" in existing.read_text()


def test_materialize_githooks_overwrites_own_previous_version(tmp_path):
    """When the existing pre-commit was authored by the factory itself
    (carries the `factory: dream-team` banner), overwriting is safe."""
    materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    # Re-run should not raise.
    materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today="2027-01-01", fv="0.9.1", gv=GV,
    )
    text = (tmp_path / ".githooks/pre-commit").read_text()
    assert "factory-version: 0.9.1" in text


def test_materialize_githooks_pre_commit_probes_for_python3(tmp_path):
    """The entry must noop gracefully when python3 isn't on PATH instead of
    failing with exit 127."""
    materialize.materialize_githooks(
        PLUGIN_ROOT, tmp_path,
        dry_run=False, today=TODAY, fv=FV, gv=GV,
    )
    text = (tmp_path / ".githooks/pre-commit").read_text()
    assert "command -v python3" in text
    # When the probe fails, exit 0 — fail open, not closed.
    assert "exit 0" in text


# --------------------------------------------------------------------------
# read_plugin_metadata
# --------------------------------------------------------------------------

def test_read_plugin_metadata_returns_factory_version():
    meta = materialize.read_plugin_metadata(PLUGIN_ROOT)
    assert "factory-version" in meta
    assert meta["factory-version"]  # non-empty
    assert "generator-version" in meta
