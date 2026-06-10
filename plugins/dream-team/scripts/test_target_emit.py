"""Layer-1 unit tests for `target_emit.py` — the cross-IDE format
transforms used by the materializer.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import target_emit  # noqa: E402


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------

def test_split_frontmatter_basic():
    text = "---\nname: kent-beck\ndescription: TDD principles\n---\nBody."
    fields, _, body = target_emit.split_frontmatter(text)
    assert fields["name"] == "kent-beck"
    assert fields["description"] == "TDD principles"
    assert body == "Body."


def test_split_frontmatter_no_frontmatter_returns_body():
    text = "Just markdown.\n"
    fields, raw, body = target_emit.split_frontmatter(text)
    assert fields == {}
    assert raw == ""
    assert body == text


def test_split_frontmatter_handles_quoted_values():
    text = "---\nname: 'Kent Beck'\ndescription: \"With colons: yes\"\n---\nB"
    fields, _, _ = target_emit.split_frontmatter(text)
    assert fields["name"] == "Kent Beck"
    assert fields["description"] == "With colons: yes"


def test_split_frontmatter_handles_folded_scalar():
    text = (
        "---\n"
        "name: team-update\n"
        "description: >-\n"
        "  Long\n"
        "  description.\n"
        "---\n"
        "Body"
    )
    fields, _, _ = target_emit.split_frontmatter(text)
    assert fields["description"] == "Long description."


def test_split_frontmatter_skips_lists_and_nested():
    text = (
        "---\n"
        "name: foo\n"
        "description: bar\n"
        "allowed-tools:\n"
        "  - Read\n"
        "  - Write\n"
        "domains: ['eng', 'tdd']\n"
        "---\n"
        "B"
    )
    fields, _, _ = target_emit.split_frontmatter(text)
    assert fields == {"name": "foo", "description": "bar"}


# --------------------------------------------------------------------------
# Skill emit — claude / cursor / copilot
# --------------------------------------------------------------------------

CANONICAL_SKILL = (
    "---\n"
    "name: kent-beck\n"
    "tier: 3\n"
    "factory: 'dream-team'\n"
    "factory-version: '0.8.0'\n"
    "generated-by: 'team-member-recruit'\n"
    "description: TDD, refactoring, simple design.\n"
    "allowed-tools:\n"
    "  - Read\n"
    "  - Write\n"
    "---\n"
    "<extends>team-engineering/SKILL.md</extends>\n"
    "\n"
    "# Kent Beck\n"
    "Body content.\n"
)


def test_emit_skill_claude_returns_content_verbatim():
    path, content = target_emit.emit_skill("claude", CANONICAL_SKILL, "kent-beck")
    assert path == ".claude/skills/kent-beck/SKILL.md"
    assert content == CANONICAL_SKILL


def test_emit_skill_cursor_strips_to_name_and_description():
    path, content = target_emit.emit_skill("cursor", CANONICAL_SKILL, "kent-beck")
    assert path == ".cursor/skills/kent-beck/SKILL.md"
    fields, _, body = target_emit.split_frontmatter(content)
    assert fields == {"name": "kent-beck", "description": "TDD, refactoring, simple design."}
    # Provenance and allowed-tools stripped.
    assert "factory-version" not in content
    assert "allowed-tools" not in content
    # Body preserved verbatim.
    assert body.startswith("<extends>team-engineering/SKILL.md</extends>")
    assert "Body content." in body


def test_emit_skill_copilot_uses_folded_description_when_long():
    long_desc = "x " * 50  # > 80 chars
    content_long = CANONICAL_SKILL.replace(
        "description: TDD, refactoring, simple design.",
        f"description: {long_desc.strip()}",
    )
    path, content = target_emit.emit_skill("copilot", content_long, "kent-beck")
    assert path == ".github/skills/kent-beck/SKILL.md"
    assert "description: >-" in content
    # Folded body preserves the content (re-parsed should round-trip).
    fields, _, _ = target_emit.split_frontmatter(content)
    assert fields["description"] == long_desc.strip()


def test_emit_skill_copilot_uses_inline_for_short_descriptions():
    path, content = target_emit.emit_skill("copilot", CANONICAL_SKILL, "kent-beck")
    assert path == ".github/skills/kent-beck/SKILL.md"
    # Short description → inline
    assert "description: >-" not in content
    assert "description: TDD" in content


def test_emit_skill_fallback_name_used_when_frontmatter_missing_name():
    bare = "---\ndescription: A skill.\n---\nBody"
    _, content = target_emit.emit_skill("cursor", bare, "my-slug")
    fields, _, _ = target_emit.split_frontmatter(content)
    assert fields["name"] == "my-slug"


# --------------------------------------------------------------------------
# Command emit
# --------------------------------------------------------------------------

CANONICAL_COMMAND = (
    "---\n"
    "name: dream-team:recruit\n"
    "description: Recruit a new team-member.\n"
    "argument-hint: \"<name or domain>\"\n"
    "allowed-tools:\n"
    "  - Read\n"
    "  - Write\n"
    "---\n"
    "<objective>\n"
    "Add a new team-member.\n"
    "</objective>\n"
)


def test_emit_command_claude_verbatim():
    path, content = target_emit.emit_command("claude", CANONICAL_COMMAND, "recruit")
    assert path == ".claude/commands/recruit.md"
    assert content == CANONICAL_COMMAND


def test_emit_command_cursor_drops_name_keeps_description():
    path, content = target_emit.emit_command("cursor", CANONICAL_COMMAND, "recruit")
    assert path == ".cursor/commands/recruit.md"
    fields, _, body = target_emit.split_frontmatter(content)
    assert "name" not in fields
    assert fields["description"] == "Recruit a new team-member."
    assert "argument-hint" not in content
    assert "<objective>" in body


def test_emit_command_copilot_uses_prompt_md_extension():
    path, _ = target_emit.emit_command("copilot", CANONICAL_COMMAND, "recruit")
    assert path == ".github/prompts/recruit.prompt.md"


# --------------------------------------------------------------------------
# Agent emit — claude-only
# --------------------------------------------------------------------------

def test_emit_agent_claude_returns_path():
    result = target_emit.emit_agent("claude", "---\nname: orch\n---\nBody", "orchestrator")
    assert result is not None
    path, content = result
    assert path == ".claude/agents/orchestrator.md"


def test_emit_agent_cursor_returns_none():
    assert target_emit.emit_agent("cursor", "anything", "orchestrator") is None


def test_emit_agent_copilot_returns_none():
    assert target_emit.emit_agent("copilot", "anything", "orchestrator") is None


# --------------------------------------------------------------------------
# Reference emit — mirrored byte-identical
# --------------------------------------------------------------------------

def test_emit_reference_byte_identical_across_targets():
    text = "# Principles\nBeck believes in tight feedback loops.\n"
    for target, prefix in [
        ("claude", ".claude/skills"),
        ("cursor", ".cursor/skills"),
        ("copilot", ".github/skills"),
    ]:
        path, content = target_emit.emit_reference(target, text, "kent-beck", "references/principles.md")
        assert path == f"{prefix}/kent-beck/references/principles.md"
        assert content == text


# --------------------------------------------------------------------------
# Self-sufficiency — no plugin-root literals leak through
# --------------------------------------------------------------------------

def test_emit_does_not_inject_plugin_root_literals():
    """Defense-in-depth: even if upstream stamps were wrong, the transforms
    don't introduce ${CLAUDE_PLUGIN_ROOT} or plugin tree paths."""
    for target in target_emit.ALL_TARGETS:
        _, sk = target_emit.emit_skill(target, CANONICAL_SKILL, "kent-beck")
        assert "${CLAUDE_PLUGIN_ROOT}" not in sk
        assert "plugins/dream-team" not in sk
        _, cmd = target_emit.emit_command(target, CANONICAL_COMMAND, "recruit")
        assert "${CLAUDE_PLUGIN_ROOT}" not in cmd
        assert "plugins/dream-team" not in cmd


def test_all_targets_constant_is_complete():
    assert set(target_emit.ALL_TARGETS) == {"claude", "cursor", "copilot"}


# --------------------------------------------------------------------------
# Phase 5.1 — YAML round-trip correctness
# --------------------------------------------------------------------------

def test_apostrophe_in_description_round_trips():
    """A description with an apostrophe ('Kent Beck's TDD') survives the
    Cursor transform without becoming 'Kent Beck''s TDD' on re-parse."""
    src = (
        "---\nname: kent-beck\n"
        "description: Kent Beck's principled approach to TDD.\n"
        "---\nBody"
    )
    _, content = target_emit.emit_skill("cursor", src, "kent-beck")
    fields, _, _ = target_emit.split_frontmatter(content)
    assert fields["description"] == "Kent Beck's principled approach to TDD."


def test_double_quoted_value_with_escape_round_trips():
    src = (
        "---\nname: x\n"
        'description: "She said \\"hi\\""\n'
        "---\nBody"
    )
    fields, _, _ = target_emit.split_frontmatter(src)
    assert fields["description"] == 'She said "hi"'


def test_description_starting_with_dash_gets_quoted():
    src = (
        "---\nname: x\n"
        "description: -starts with dash\n"
        "---\nBody"
    )
    _, content = target_emit.emit_skill("cursor", src, "x")
    # The output value MUST be quoted — otherwise YAML reads `-` as a list
    # marker and the frontmatter is malformed.
    assert "description: '-starts with dash'" in content


def test_description_that_is_a_yaml_separator_gets_quoted():
    src = "---\nname: x\ndescription: ---\n---\nBody"
    _, content = target_emit.emit_skill("cursor", src, "x")
    assert "description: '---'" in content


def test_description_that_looks_like_bool_gets_quoted():
    for val in ("true", "false", "yes", "no", "off", "null"):
        src = f"---\nname: x\ndescription: {val}\n---\nBody"
        _, content = target_emit.emit_skill("cursor", src, "x")
        assert f"description: '{val}'" in content, val


def test_description_that_looks_like_number_gets_quoted():
    src = "---\nname: x\ndescription: 42\n---\nBody"
    _, content = target_emit.emit_skill("cursor", src, "x")
    assert "description: '42'" in content


def test_description_with_colon_still_quoted():
    src = "---\nname: x\ndescription: foo: bar baz\n---\nBody"
    _, content = target_emit.emit_skill("cursor", src, "x")
    # The original had a colon — needs single quoting.
    assert "description: 'foo: bar baz'" in content


# --------------------------------------------------------------------------
# Phase 5.1 — slug path-traversal guards
# --------------------------------------------------------------------------

def test_emit_skill_rejects_path_traversal_slug():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_skill("claude", CANONICAL_SKILL, "../etc/passwd")


def test_emit_skill_rejects_absolute_slug():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_skill("claude", CANONICAL_SKILL, "/abs/path")


def test_emit_skill_rejects_slug_with_slash():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_skill("cursor", CANONICAL_SKILL, "nested/slug")


def test_emit_skill_accepts_normal_slugs():
    target_emit.emit_skill("claude", CANONICAL_SKILL, "kent-beck")
    target_emit.emit_skill("claude", CANONICAL_SKILL, "team-engineering")
    target_emit.emit_skill("claude", CANONICAL_SKILL, "Lisa.Crispin")  # dots ok


def test_emit_command_rejects_path_traversal_verb():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_command("claude", CANONICAL_COMMAND, "../escape")


def test_emit_reference_rejects_traversal_subpath():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_reference(
            "claude", "x", "kent-beck", "../../escape.md"
        )


def test_emit_reference_rejects_absolute_subpath():
    import pytest
    with pytest.raises(ValueError):
        target_emit.emit_reference(
            "claude", "x", "kent-beck", "/abs.md"
        )
