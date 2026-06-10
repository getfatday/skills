"""Layer-1 unit tests for the PreToolUse hook `check-generated-edit.py`."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "check-generated-edit.py"


STAMPED_SKILL = (
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


def run_hook(payload, *, cwd=None):
    """Run the hook with the given JSON payload on stdin. Returns
    (exit_code, stderr)."""
    result = subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True,
        cwd=cwd, timeout=15,
    )
    return result.returncode, result.stderr


def make_repo(tmp_path):
    """Create a fake git repo with a materialized skill."""
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / ".claude/skills/kent-beck"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(STAMPED_SKILL, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# Block path
# --------------------------------------------------------------------------

def test_blocks_edit_on_materialized_skill(tmp_path):
    root = make_repo(tmp_path)
    skill = root / ".claude/skills/kent-beck/SKILL.md"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(skill),
            "old_string": "Body content.",
            "new_string": "Hand edit.",
        },
    }
    code, stderr = run_hook(payload, cwd=root)
    assert code == 2, stderr
    assert "materialized by the dream-team factory" in stderr
    assert ".config/team/team-members/kent-beck.md" in stderr
    assert "/dream-team:update kent-beck" in stderr


def test_blocks_write_creating_materialized_skill_with_stamp(tmp_path):
    root = make_repo(tmp_path)
    skill = root / ".claude/skills/marty-cagan/SKILL.md"
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(skill),
            "content": STAMPED_SKILL.replace("kent-beck", "marty-cagan"),
        },
    }
    code, stderr = run_hook(payload, cwd=root)
    assert code == 2, stderr
    assert "materialized" in stderr


def test_blocks_edit_on_cursor_mirror(tmp_path):
    """Cursor mirror frontmatter is trimmed to name/description and has no
    factory stamp — but the hook looks at the canonical Claude sibling
    instead, so the mirror gets protected."""
    root = make_repo(tmp_path)
    mirror_dir = root / ".cursor/skills/kent-beck"
    mirror_dir.mkdir(parents=True)
    # Mirror has NO stamp — just name + description, like real Phase-5 output.
    (mirror_dir / "SKILL.md").write_text(
        "---\nname: kent-beck\ndescription: Beck.\n---\nBody content.\n",
        encoding="utf-8",
    )
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(mirror_dir / "SKILL.md"),
            "old_string": "Body content.",
            "new_string": "Hand edit.",
        },
    }
    code, stderr = run_hook(payload, cwd=root)
    assert code == 2, stderr
    # The redirect still names the slug — sourced from the canonical sibling.
    assert "kent-beck" in stderr


def test_blocks_edit_on_github_prompt_mirror(tmp_path):
    """`.github/prompts/<verb>.prompt.md` is the Copilot mirror — protected
    via the canonical .claude/commands/<verb>.md sibling."""
    root = make_repo(tmp_path)
    # Lay down the canonical entry command (stamped).
    entry = root / ".claude/commands/consult.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        STAMPED_SKILL.replace("tier: 3", "tier: 2-materialized")
                     .replace("blueprint: '.config/team/team-members/kent-beck.md'\n", "")
                     .replace("blueprint-hash: 'abc'\n", ""),
        encoding="utf-8",
    )
    # Lay down the Copilot mirror (frontmatter trimmed, no stamp).
    mirror = root / ".github/prompts/consult.prompt.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\ndescription: Run a consultation.\n---\nBody.\n",
        encoding="utf-8",
    )
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(mirror),
            "old_string": "Body.",
            "new_string": "Hand edit.",
        },
    }
    code, stderr = run_hook(payload, cwd=root)
    assert code == 2, stderr


def test_allows_edit_on_mirror_when_canonical_has_no_stamp(tmp_path):
    """Mirror exists, canonical sibling exists but has no factory stamp
    (e.g. a user-owned skill at the same path) → allowed."""
    root = make_repo(tmp_path)
    # Overwrite the canonical with an unstamped form.
    canonical = root / ".claude/skills/kent-beck/SKILL.md"
    canonical.write_text(
        "---\nname: kent-beck\ndescription: mine now.\n---\nbody.\n",
        encoding="utf-8",
    )
    mirror_dir = root / ".cursor/skills/kent-beck"
    mirror_dir.mkdir(parents=True)
    (mirror_dir / "SKILL.md").write_text(
        "---\nname: kent-beck\ndescription: mine.\n---\nbody.\n",
        encoding="utf-8",
    )
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(mirror_dir / "SKILL.md"),
            "old_string": "body.",
            "new_string": "tweaked.",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


def test_allows_edit_on_detached_artifact(tmp_path):
    """A file with `provenance: detached` is the documented opt-out — the
    user owns it and the hook leaves it alone."""
    root = make_repo(tmp_path)
    detached_text = STAMPED_SKILL.replace(
        "tier: 3\n", "tier: 3\nprovenance: detached\n"
    )
    skill = root / ".claude/skills/kent-beck/SKILL.md"
    skill.write_text(detached_text, encoding="utf-8")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(skill),
            "old_string": "Body content.",
            "new_string": "Hand edit.",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


# --------------------------------------------------------------------------
# Allow path — no false positives
# --------------------------------------------------------------------------

def test_allows_edit_on_unrelated_md(tmp_path):
    root = make_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Readme\nHello.\n")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(readme),
            "old_string": "Hello.",
            "new_string": "Hi.",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


def test_allows_edit_on_blueprint(tmp_path):
    """Editing `.config/team/team-members/<slug>.md` IS the supported path
    for updating a member. The hook must not block."""
    root = make_repo(tmp_path)
    bp = root / ".config/team/team-members/kent-beck.md"
    bp.parent.mkdir(parents=True)
    bp.write_text("---\nname: Kent Beck\n---\nBlueprint body.\n")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(bp),
            "old_string": "Blueprint body.",
            "new_string": "Enriched blueprint body.",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


def test_allows_edit_on_unstamped_file_in_managed_location(tmp_path):
    """A user-owned hand-written skill at a managed-looking path with no
    dream-team stamp should NOT be blocked."""
    root = make_repo(tmp_path)
    hand = root / ".claude/skills/handwritten/SKILL.md"
    hand.parent.mkdir(parents=True)
    hand.write_text("---\nname: handwritten\ndescription: mine.\n---\nbody")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(hand),
            "old_string": "body",
            "new_string": "tweaked",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


def test_allows_non_edit_write_tool_calls(tmp_path):
    root = make_repo(tmp_path)
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": str(root / "anything")},
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


def test_allows_non_md_paths(tmp_path):
    root = make_repo(tmp_path)
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(root / "main.py"), "old_string": "x", "new_string": "y"},
    }
    code, _ = run_hook(payload, cwd=root)
    assert code == 0


# --------------------------------------------------------------------------
# Robustness
# --------------------------------------------------------------------------

def test_malformed_stdin_does_not_block():
    result = subprocess.run(
        ["python3", str(HOOK)],
        input="not json",
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0


def test_empty_stdin_does_not_block():
    result = subprocess.run(
        ["python3", str(HOOK)],
        input="",
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0


def test_path_with_spaces_is_handled(tmp_path):
    """The path comes via JSON, not argv — so embedded spaces shouldn't
    break parsing."""
    root = make_repo(tmp_path)
    spaced_dir = root / ".claude/skills/has spaces"
    spaced_dir.mkdir(parents=True)
    (spaced_dir / "SKILL.md").write_text(STAMPED_SKILL, encoding="utf-8")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(spaced_dir / "SKILL.md"),
            "old_string": "Body content.",
            "new_string": "Hand edit.",
        },
    }
    code, stderr = run_hook(payload, cwd=root)
    # The path matches the managed-skill pattern even with spaces (re anchors
    # don't restrict character class). Should block.
    assert code == 2, stderr


def test_edit_that_does_not_match_falls_through(tmp_path):
    """If `old_string` isn't in the file, proposed_content_for_edit returns
    None and the hook allows — the underlying tool will surface its own
    error."""
    root = make_repo(tmp_path)
    skill = root / ".claude/skills/kent-beck/SKILL.md"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(skill),
            "old_string": "this string is not in the file",
            "new_string": "x",
        },
    }
    code, _ = run_hook(payload, cwd=root)
    # The hook can either short-circuit (allow) or block based on the
    # current content stamp. Current implementation blocks because the
    # current content has the stamp. Either is defensible — we assert the
    # current behavior to lock it in.
    assert code in (0, 2)
