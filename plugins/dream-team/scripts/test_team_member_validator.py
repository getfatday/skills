"""Layer-1 unit tests for `team_member_validator.py`."""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import team_member_validator as tmv  # noqa: E402


STAMPED = (
    "---\n"
    "name: kent-beck\n"
    "factory: dream-team\n"
    "factory-version: '0.9.0'\n"
    "generated-by: 'team-member-recruit'\n"
    "generator-version: '0.1'\n"
    "source: 'templates/team-members/kent-beck/skills/kent-beck/SKILL.md'\n"
    "materialized: '2026-06-08'\n"
    "tier: 3\n"
    "blueprint: '.config/team/team-members/kent-beck.md'\n"
    "blueprint-hash: 'abc'\n"
    "---\n"
    "Body content.\n"
)

UNSTAMPED = (
    "---\nname: hand-written\ndescription: just a skill.\n---\nbody.\n"
)

DETACHED = (
    "---\nname: kent-beck\nfactory: dream-team\nprovenance: detached\n---\nbody.\n"
)


# --------------------------------------------------------------------------
# is_managed_path
# --------------------------------------------------------------------------

def test_managed_path_claude_skill():
    assert tmv.is_managed_path(".claude/skills/kent-beck/SKILL.md")


def test_managed_path_claude_skill_reference():
    assert tmv.is_managed_path(".claude/skills/kent-beck/references/principles.md")


def test_managed_path_team_assemble_pattern():
    assert tmv.is_managed_path(".claude/skills/team-assemble/patterns/debate.md")


def test_managed_path_cursor_mirror():
    assert tmv.is_managed_path(".cursor/skills/kent-beck/SKILL.md")


def test_managed_path_github_mirror():
    assert tmv.is_managed_path(".github/skills/kent-beck/SKILL.md")


def test_managed_path_claude_entry_command():
    for verb in ("consult", "coach", "plan", "review"):
        assert tmv.is_managed_path(f".claude/commands/{verb}.md"), verb


def test_managed_path_github_prompt_extension():
    assert tmv.is_managed_path(".github/prompts/consult.prompt.md")


def test_managed_path_claude_orchestrator_agent():
    assert tmv.is_managed_path(".claude/agents/orchestrator.md")


def test_unmanaged_paths_left_alone():
    # Hand-written skill (not under skills/<slug>/SKILL.md pattern? actually it IS)
    # — Let's pick truly unrelated paths.
    assert not tmv.is_managed_path("README.md")
    assert not tmv.is_managed_path(".config/team/team-members/kent-beck.md")
    assert not tmv.is_managed_path(".claude/commands/recruit.md")  # factory cmd
    assert not tmv.is_managed_path(".claude/agents/other-agent.md")
    assert not tmv.is_managed_path("")


def test_managed_path_accepts_dot_slash_prefix():
    assert tmv.is_managed_path("./.claude/skills/kent-beck/SKILL.md")


# --------------------------------------------------------------------------
# parse_provenance
# --------------------------------------------------------------------------

def test_parse_provenance_returns_dict_for_stamped():
    stamp = tmv.parse_provenance(STAMPED)
    assert stamp is not None
    assert stamp["factory"] == "dream-team"
    assert stamp["factory-version"] == "0.9.0"


def test_parse_provenance_returns_none_for_unstamped():
    assert tmv.parse_provenance(UNSTAMPED) is None


def test_parse_provenance_returns_none_for_other_factory():
    other = STAMPED.replace("factory: dream-team", "factory: 'document'")
    assert tmv.parse_provenance(other) is None


def test_parse_provenance_returns_none_for_no_frontmatter():
    assert tmv.parse_provenance("just plain markdown") is None


def test_parse_provenance_handles_apostrophe_in_value():
    text = STAMPED.replace(
        "source: 'templates/team-members/kent-beck/skills/kent-beck/SKILL.md'",
        "source: 'Beck''s template'",
    )
    stamp = tmv.parse_provenance(text)
    assert stamp["source"] == "Beck's template"


# --------------------------------------------------------------------------
# check_direct_edit
# --------------------------------------------------------------------------

def test_check_direct_edit_blocks_stamped_managed_path():
    v = tmv.check_direct_edit(".claude/skills/kent-beck/SKILL.md", STAMPED)
    assert v is not None
    assert v.code == "DT-EDIT"
    # The redirect must name the blueprint and the slug-aware update command.
    assert ".config/team/team-members/kent-beck.md" in v.message
    assert "kent-beck" in v.message
    assert "/dream-team:update" in v.message


def test_check_direct_edit_allows_unstamped_files_even_in_managed_locations():
    # The user might place an unrelated SKILL.md at the same location — if it
    # has no dream-team stamp, it's user-owned.
    v = tmv.check_direct_edit(
        ".claude/skills/kent-beck/SKILL.md", UNSTAMPED
    )
    assert v is None


def test_check_direct_edit_allows_unmanaged_paths():
    v = tmv.check_direct_edit("README.md", STAMPED)
    assert v is None


def test_check_direct_edit_allows_detached_opt_out():
    """`provenance: detached` is the documented opt-out — once set, the
    user owns the file and the hook leaves it alone."""
    v = tmv.check_direct_edit(".claude/skills/kent-beck/SKILL.md", DETACHED)
    assert v is None


# --------------------------------------------------------------------------
# canonical_path_for — mirror → claude sibling
# --------------------------------------------------------------------------

def test_canonical_path_for_cursor_skill():
    assert tmv.canonical_path_for(
        ".cursor/skills/kent-beck/SKILL.md"
    ) == ".claude/skills/kent-beck/SKILL.md"


def test_canonical_path_for_cursor_command():
    assert tmv.canonical_path_for(
        ".cursor/commands/consult.md"
    ) == ".claude/commands/consult.md"


def test_canonical_path_for_github_skill():
    assert tmv.canonical_path_for(
        ".github/skills/kent-beck/references/principles.md"
    ) == ".claude/skills/kent-beck/references/principles.md"


def test_canonical_path_for_github_prompt_extension_strip():
    """Copilot uses .prompt.md — the canonical form drops it."""
    assert tmv.canonical_path_for(
        ".github/prompts/consult.prompt.md"
    ) == ".claude/commands/consult.md"


def test_canonical_path_for_claude_form_returns_none():
    """A Claude-form path has no canonical sibling — it IS the canonical."""
    assert tmv.canonical_path_for(".claude/skills/kent-beck/SKILL.md") is None


def test_canonical_path_for_unrelated_path_returns_none():
    assert tmv.canonical_path_for("README.md") is None


def test_canonical_path_for_accepts_dot_slash_prefix():
    assert tmv.canonical_path_for(
        "./.cursor/skills/kent-beck/SKILL.md"
    ) == ".claude/skills/kent-beck/SKILL.md"


def test_check_direct_edit_team_skill_redirects_to_team_blueprint():
    stamped_team = STAMPED.replace(
        "blueprint: '.config/team/team-members/kent-beck.md'",
        "blueprint: '.config/team/teams/engineering.md'",
    )
    v = tmv.check_direct_edit(
        ".claude/skills/team-engineering/SKILL.md", stamped_team
    )
    assert v is not None
    # Redirect should name the team blueprint path
    assert ".config/team/teams/engineering.md" in v.message


def test_check_direct_edit_entry_command_redirects_to_factory_update():
    stamped_cmd = STAMPED.replace(
        "blueprint: '.config/team/team-members/kent-beck.md'\n", ""
    ).replace("blueprint-hash: 'abc'\n", "").replace("tier: 3\n", "tier: 2-materialized\n")
    v = tmv.check_direct_edit(".claude/commands/consult.md", stamped_cmd)
    assert v is not None
    # No per-slug blueprint for entry commands — redirect to `/dream-team:update`.
    assert "/dream-team:update" in v.message


def test_check_direct_edit_orchestrator_redirects_without_per_slug_blueprint():
    stamped_orch = STAMPED.replace("tier: 3", "tier: 2-materialized")
    v = tmv.check_direct_edit(".claude/agents/orchestrator.md", stamped_orch)
    assert v is not None
    assert "/dream-team:update" in v.message


# --------------------------------------------------------------------------
# Self-sanity for the validator's own factory name
# --------------------------------------------------------------------------

def test_factory_name_constant_matches_plugin_json():
    import json
    plugin_json = json.loads(
        (HERE.parent / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert tmv.FACTORY_NAME == plugin_json["name"]
