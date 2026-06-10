"""Layer-1 tests for check-document-staged.py (git pre-commit).

Each test stages a tiny typed-document portfolio in a temp git repo,
stages the file under test, runs the hook as a subprocess, and asserts
on exit code + stderr.

Uses real git (not a mock) because most of the script's value is in its
git-CLI interaction — index walk, `git show :path`, repo-root
resolution. A mocked test would assert the wrong things.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

HOOK = pathlib.Path(__file__).parent / "check-document-staged.py"


# ---------- fixtures ----------------------------------------------------

@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch git repo with one `task` type definition committed."""
    root = tmp_path / "portfolio"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"],
                   cwd=root, check=True)

    types = root / ".config" / "documents" / "types"
    types.mkdir(parents=True)
    (types / "task.md").write_text(
        "## Identity\n"
        "- name: task\n\n"
        "## Fields\n"
        "### Required\n"
        "- `owner: string` — task owner\n"
        "- `due: date` — when it's due\n\n"
        "## Sections\n"
        "### Required\n"
        "- `## Description` — what needs doing\n"
        "- `## Acceptance Criteria` — done means\n\n"
        "## Lifecycle\n"
        "- values: pending, active, done\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=root, check=True)
    return root


def good_doc() -> str:
    return (
        "---\n"
        "type: task\n"
        "owner: alice\n"
        "due: 2026-06-01\n"
        "status: pending\n"
        "---\n"
        "# A task\n\n"
        "## Description\n"
        "What needs doing.\n\n"
        "## Acceptance Criteria\n"
        "Done means…\n"
    )


def stage(repo: pathlib.Path, rel: str, content: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--", rel], cwd=repo, check=True)


def run_hook(repo: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=repo, capture_output=True, text=True, timeout=30,
    )


# ---------- allowed cases ----------------------------------------------

def test_no_staged_md_passes(repo):
    stage(repo, "README.txt", "no md here")
    r = run_hook(repo)
    assert r.returncode == 0, r.stderr


def test_clean_staged_doc_passes(repo):
    stage(repo, "tasks/t1.md", good_doc())
    r = run_hook(repo)
    assert r.returncode == 0, r.stderr


def test_untyped_md_passes(repo):
    stage(repo, "notes.md", "# untyped notes\nthoughts\n")
    r = run_hook(repo)
    assert r.returncode == 0, r.stderr


def test_no_config_dir_passes(tmp_path):
    root = tmp_path / "norepo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    stage(root, "x.md", "---\ntype: task\n---\n")
    r = run_hook(root)
    assert r.returncode == 0, r.stderr


def test_outside_git_repo_passes(tmp_path):
    # No git init at all.
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path, capture_output=True, text=True, timeout=20,
    )
    assert r.returncode == 0, r.stderr


# ---------- G4: unknown type --------------------------------------------

def test_g4_unknown_type_blocks(repo):
    bad = good_doc().replace("type: task", "type: planning-guide")
    stage(repo, "tasks/x.md", bad)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "planning-guide" in r.stderr
    assert "tasks/x.md" in r.stderr
    assert "G4" in r.stderr


# ---------- G5: missing required field ----------------------------------

def test_g5_missing_field_blocks(repo):
    bad = (
        "---\n"
        "type: task\n"
        "owner: alice\n"
        "status: pending\n"
        "---\n"
        "## Description\nx\n\n## Acceptance Criteria\ny\n"
    )
    stage(repo, "tasks/y.md", bad)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "due" in r.stderr
    assert "tasks/y.md" in r.stderr


# ---------- G6: missing required section --------------------------------

def test_g6_missing_section_blocks(repo):
    bad = (
        "---\n"
        "type: task\n"
        "owner: alice\n"
        "due: 2026-06-01\n"
        "status: pending\n"
        "---\n"
        "## Description\nx\n"
    )
    stage(repo, "tasks/z.md", bad)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "Acceptance Criteria" in r.stderr


# ---------- G7: off-lifecycle status ------------------------------------

def test_g7_off_lifecycle_status_blocks(repo):
    bad = good_doc().replace("status: pending", "status: 🟢 On Track")
    stage(repo, "tasks/q.md", bad)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "lifecycle" in r.stderr or "Allowed values" in r.stderr


# ---------- multi-file aggregation --------------------------------------

def test_multiple_files_all_reported(repo):
    bad1 = good_doc().replace("status: pending", "status: weird")
    bad2 = good_doc().replace("type: task", "type: nope")
    stage(repo, "tasks/a.md", bad1)
    stage(repo, "tasks/b.md", bad2)
    r = run_hook(repo)
    assert r.returncode == 1
    assert "tasks/a.md" in r.stderr
    assert "tasks/b.md" in r.stderr
    assert "failed for 2 files" in r.stderr


# ---------- index vs working tree --------------------------------------

def test_hook_validates_staged_not_worktree(repo):
    """The hook must look at the *index* content, not the worktree.

    Stage a clean doc, then dirty the worktree with an invalid version.
    The hook must pass — only the staged version matters.
    """
    f = repo / "tasks" / "w.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc(), encoding="utf-8")
    subprocess.run(["git", "add", "--", "tasks/w.md"], cwd=repo, check=True)
    # Dirty the worktree
    f.write_text(good_doc().replace("type: task", "type: bogus"),
                 encoding="utf-8")
    r = run_hook(repo)
    assert r.returncode == 0, r.stderr


def test_hook_catches_invalid_index_with_clean_worktree(repo):
    """Inverse — staged bad, worktree clean: hook still blocks."""
    f = repo / "tasks" / "i.md"
    f.parent.mkdir(parents=True)
    bad = good_doc().replace("type: task", "type: bogus")
    f.write_text(bad, encoding="utf-8")
    subprocess.run(["git", "add", "--", "tasks/i.md"], cwd=repo, check=True)
    # Restore worktree to clean
    f.write_text(good_doc(), encoding="utf-8")
    r = run_hook(repo)
    assert r.returncode == 1
    assert "bogus" in r.stderr


# ---------- deletions are ignored --------------------------------------

def test_deletion_ignored(repo):
    # Seed a doc, commit, then stage deletion.
    f = repo / "tasks" / "del.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc(), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=repo, check=True)
    f.unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    r = run_hook(repo)
    # Deletion of a doc isn't a content-integrity issue.
    assert r.returncode == 0, r.stderr
