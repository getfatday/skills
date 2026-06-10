"""Layer-1 tests for the pre-commit hook `check-blueprint-staged.py`.

These tests build a real git repo per-case using subprocess (no GitPython
dependency), stage a file, and run the hook against it. Slow per-test —
each one does 3-5 git commands — but they're the only honest test for a
hook that consults `git diff --cached`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "check-blueprint-staged.py"


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


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=cwd, capture_output=True, text=True, check=check, timeout=15,
    )


def init_repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    return tmp_path


def run_hook(repo):
    result = subprocess.run(
        ["python3", str(HOOK)],
        cwd=repo, capture_output=True, text=True, timeout=15,
    )
    return result.returncode, result.stderr


# --------------------------------------------------------------------------
# Block path
# --------------------------------------------------------------------------

def test_blocks_staged_edit_of_materialized_skill(tmp_path):
    repo = init_repo(tmp_path)
    skill = repo / ".claude/skills/kent-beck/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(STAMPED_SKILL, encoding="utf-8")
    git(repo, "add", str(skill))
    git(repo, "commit", "-q", "-m", "initial materialize")
    # Now hand-edit.
    skill.write_text(STAMPED_SKILL.replace("Body content.", "Hand edit."))
    git(repo, "add", str(skill))

    code, stderr = run_hook(repo)
    assert code == 1
    assert "dream-team blueprint integrity" in stderr
    assert "kent-beck" in stderr
    assert "/dream-team:update kent-beck" in stderr
    # The bypass instructions name --no-verify by name.
    assert "--no-verify" in stderr


def test_blocks_new_staged_materialized_file_with_stamp(tmp_path):
    repo = init_repo(tmp_path)
    skill = repo / ".claude/skills/new-member/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(STAMPED_SKILL.replace("kent-beck", "new-member"),
                     encoding="utf-8")
    git(repo, "add", str(skill))

    code, stderr = run_hook(repo)
    assert code == 1
    assert "new-member" in stderr


# --------------------------------------------------------------------------
# Allow path
# --------------------------------------------------------------------------

def test_allows_blueprint_edit(tmp_path):
    """Editing the blueprint at `.config/team/team-members/<slug>.md` IS the
    supported path. The pre-commit hook must not block."""
    repo = init_repo(tmp_path)
    bp = repo / ".config/team/team-members/kent-beck.md"
    bp.parent.mkdir(parents=True)
    bp.write_text("---\nname: Kent Beck\n---\nBlueprint body.\n")
    git(repo, "add", str(bp))

    code, _ = run_hook(repo)
    assert code == 0


def test_allows_unstamped_md_in_managed_location(tmp_path):
    """An unstamped file in a managed location is user-owned and allowed."""
    repo = init_repo(tmp_path)
    md = repo / ".claude/skills/handwritten/SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\nname: handwritten\ndescription: mine.\n---\nbody\n")
    git(repo, "add", str(md))

    code, _ = run_hook(repo)
    assert code == 0


def test_allows_unrelated_md_changes(tmp_path):
    repo = init_repo(tmp_path)
    readme = repo / "README.md"
    readme.write_text("# Hi\n")
    git(repo, "add", str(readme))

    code, _ = run_hook(repo)
    assert code == 0


def test_allows_no_staged_files(tmp_path):
    repo = init_repo(tmp_path)
    code, _ = run_hook(repo)
    assert code == 0


def test_exits_zero_outside_a_repo(tmp_path):
    # tmp_path has no .git; the hook should bail.
    code, _ = run_hook(tmp_path)
    assert code == 0
