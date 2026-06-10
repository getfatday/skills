"""Layer 2 — manifest validity and consistency.

Checks the plugin manifest, the marketplace entry, the cross-IDE mirror
manifest, and basic plugin structure. Deterministic; runs on every commit.
Mirrors the logic of the `plugin-validation` CI workflow so a break is caught
locally by `make test` before it reaches CI.
"""
import json
import pathlib

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin/plugin.json"
CURSOR_PLUGIN_JSON = PLUGIN_ROOT / ".cursor-plugin/plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin/marketplace.json"

SKILL_FILES = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def test_plugin_json_valid_and_complete():
    """plugin.json is valid JSON with every field plugin-validation requires."""
    manifest = _load(PLUGIN_JSON)
    for field in ("name", "description", "version", "author"):
        assert manifest.get(field), f"plugin.json missing required field '{field}'"
    assert manifest["name"] == "document"


def test_plugin_json_declares_document_schema_version():
    """The factory needs a declared config-schema version (FACTORY.md)."""
    assert "documentSchemaVersion" in _load(PLUGIN_JSON), (
        "plugin.json must declare documentSchemaVersion"
    )


def test_no_misplaced_component_directories():
    """skills/agents/hooks/commands must live at the plugin root, never under
    .claude-plugin/ (a plugin-validation rule)."""
    for forbidden in ("skills", "agents", "hooks", "commands"):
        assert not (PLUGIN_ROOT / ".claude-plugin" / forbidden).exists(), (
            f".claude-plugin/{forbidden}/ is misplaced — move it to the plugin root"
        )


def test_marketplace_lists_document_plugin():
    """The root marketplace.json must carry a `document` entry whose source
    resolves to the real plugin.json."""
    marketplace = _load(MARKETPLACE_JSON)
    entries = {e["name"]: e for e in marketplace.get("plugins", [])}
    assert "document" in entries, "marketplace.json has no `document` entry"
    source = entries["document"]["source"].lstrip("./")
    assert (REPO_ROOT / source / ".claude-plugin/plugin.json").is_file(), (
        f"marketplace.json `document` source '{source}' has no plugin.json"
    )


def test_cursor_plugin_version_matches_claude_plugin():
    """The generated Cursor manifest must not drift from the Claude manifest."""
    assert _load(CURSOR_PLUGIN_JSON)["version"] == _load(PLUGIN_JSON)["version"], (
        ".cursor-plugin/plugin.json version is stale — run scripts/cursor-marketplace.sh"
    )


def test_skills_present():
    assert SKILL_FILES, "no skills found under plugins/document/skills/"


def test_hooks_json_wires_enforcement_hook():
    """hooks/hooks.json must register the PreToolUse Edit|Write guard backed
    by check-document-edit.py, plus the PostToolUse advisory."""
    hooks = _load(PLUGIN_ROOT / "hooks/hooks.json")
    pre = hooks["hooks"]["PreToolUse"]
    matchers = [(h["matcher"], h["hooks"][0]["command"]) for h in pre]
    assert any(
        m == "Edit|Write" and "check-document-edit.py" in cmd
        for m, cmd in matchers
    ), f"PreToolUse must register Edit|Write → check-document-edit.py, got {matchers}"

    post = hooks["hooks"]["PostToolUse"]
    assert any(
        h["matcher"] == "Write|Edit"
        and "check-lint-write.sh" in h["hooks"][0]["command"]
        for h in post
    ), "PostToolUse advisory (check-lint-write.sh) must remain registered"


def test_enforcement_hook_script_exists_and_runnable():
    """The hook command in hooks.json must resolve to a real, executable
    Python script."""
    script = PLUGIN_ROOT / "scripts/check-document-edit.py"
    assert script.is_file(), f"missing hook script: {script}"
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env python3"), (
        "hook script must start with a python3 shebang"
    )


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_frontmatter_parses(skill_md, frontmatter):
    """Every skill's SKILL.md opens with a frontmatter block carrying `name`."""
    fields = frontmatter(skill_md)
    assert fields, f"{skill_md.parent.name}: SKILL.md has no frontmatter block"
    assert fields.get("name") == skill_md.parent.name, (
        f"{skill_md.parent.name}: frontmatter `name` does not match the skill dir"
    )
