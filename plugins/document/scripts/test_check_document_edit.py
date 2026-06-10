"""Layer-1 tests for the check-document-edit.py PreToolUse hook.

Each test stages a small typed-document portfolio under tmp_path,
synthesizes a tool-call JSON payload, and invokes the hook as a
subprocess. We assert on exit code (0 = allow, 2 = block) and on the
stderr message so the block-reason stays meaningful to Claude.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

HOOK = pathlib.Path(__file__).parent / "check-document-edit.py"


# ---------- fixtures -----------------------------------------------------

@pytest.fixture
def portfolio(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch portfolio with a single `task` type definition."""
    types = tmp_path / ".config" / "documents" / "types"
    types.mkdir(parents=True)
    (types / "task.md").write_text(
        "---\n"
        "schema-version: 1\n"
        "type: task-type\n"
        "---\n"
        "# task\n\n"
        "## Identity\n"
        "- name: task\n"
        "- display: Task\n\n"
        "## Fields\n"
        "### Required\n"
        "- `owner: string` — task owner\n"
        "- `due: date` — when it's due\n"
        "### Optional\n"
        "- `priority: string` — high/med/low\n\n"
        "## Sections\n"
        "### Required\n"
        "- `## Description` — what needs doing\n"
        "- `## Acceptance Criteria` — done means\n\n"
        "## Lifecycle\n"
        "- values: pending, active, done\n",
        encoding="utf-8",
    )
    return tmp_path


def run_hook(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
    )


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


# ---------- allowed cases ------------------------------------------------

def test_non_md_file_allowed(portfolio):
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(portfolio / "notes.txt"),
                       "old_string": "a", "new_string": "b"},
    })
    assert r.returncode == 0, r.stderr


def test_unrelated_tool_allowed(portfolio):
    r = run_hook({
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    })
    assert r.returncode == 0, r.stderr


def test_no_config_dir_allowed(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("type: task\n---\nhi\n")
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(f), "content": good_doc()},
    })
    assert r.returncode == 0, r.stderr


def test_untyped_md_allowed(portfolio):
    f = portfolio / "notes.md"
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(f),
                       "content": "# untyped notes\n\njust a note.\n"},
    })
    assert r.returncode == 0, r.stderr


def test_edit_unrelated_field_allowed(portfolio):
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "What needs doing.",
                       "new_string": "What truly needs doing."},
    })
    assert r.returncode == 0, r.stderr


def test_edit_status_via_operation_artifact_allowed(portfolio):
    # An Edit that doesn't change a status line on either side should
    # not trip G1 even if the file *contains* a status line.
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "owner: alice",
                       "new_string": "owner: bob"},
    })
    # changing owner via Edit isn't covered by a guard today; Edit-other-
    # field is allowed.
    assert r.returncode == 0, r.stderr


# ---------- G1: status edit ---------------------------------------------

def test_g1_status_edit_blocked(portfolio):
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "status: pending",
                       "new_string": "status: active"},
    })
    assert r.returncode == 2
    assert "update-status" in r.stderr
    assert "status" in r.stderr


# ---------- G2: type edit -----------------------------------------------

def test_g2_type_change_blocked(portfolio):
    # Add a `project` type so the change target is valid; G2 fires on
    # the line change regardless of validity.
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "type: task",
                       "new_string": "type: initiative"},
    })
    assert r.returncode == 2
    assert "type" in r.stderr
    assert "re-classification" in r.stderr


def test_g2_type_unchanged_allowed(portfolio):
    # An Edit that touches the type: line but keeps the value identical
    # is *not* a re-classification.
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "type: task\nowner: alice",
                       "new_string": "type: task\nowner: bob"},
    })
    assert r.returncode == 0, r.stderr


# ---------- G3: Write of new typed doc ----------------------------------

def test_g3_new_typed_doc_write_blocked(portfolio):
    new = portfolio / "tasks" / "new.md"
    new.parent.mkdir(parents=True)
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(new), "content": good_doc()},
    })
    assert r.returncode == 2
    assert "/task store" in r.stderr or "/task create" in r.stderr


def test_g3_overwrite_existing_does_not_demand_create_op(portfolio):
    # Overwriting an existing doc with valid content shouldn't trip G3
    # — the doc already exists, so it isn't "creating" something new.
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(f), "content": good_doc()},
    })
    assert r.returncode == 0, r.stderr


# ---------- G4: unknown type --------------------------------------------

def test_g4_unknown_type_write_blocked(portfolio):
    new = portfolio / "notes" / "x.md"
    new.parent.mkdir(parents=True)
    bad = good_doc().replace("type: task", "type: planning-guide")
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(new), "content": bad},
    })
    assert r.returncode == 2
    assert "planning-guide" in r.stderr
    assert "/document:define" in r.stderr


# ---------- G5: missing required field ----------------------------------

def test_g5_missing_field_write_blocked(portfolio):
    new = portfolio / "tasks" / "x.md"
    new.parent.mkdir(parents=True)
    missing_due = (
        "---\n"
        "type: task\n"
        "owner: alice\n"
        "status: pending\n"
        "---\n"
        "# A task\n\n"
        "## Description\n"
        "X.\n\n"
        "## Acceptance Criteria\n"
        "Y.\n"
    )
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(new), "content": missing_due},
    })
    assert r.returncode == 2
    assert "due" in r.stderr
    assert "required field" in r.stderr


def test_g5_edit_removing_required_field_blocked(portfolio):
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    # Strip the `due:` line via Edit.
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "owner: alice\ndue: 2026-06-01\n",
                       "new_string": "owner: alice\n"},
    })
    assert r.returncode == 2
    assert "due" in r.stderr


# ---------- G6: missing required section --------------------------------

def test_g6_missing_section_write_blocked(portfolio):
    new = portfolio / "tasks" / "y.md"
    new.parent.mkdir(parents=True)
    missing_ac = (
        "---\n"
        "type: task\n"
        "owner: alice\n"
        "due: 2026-06-01\n"
        "status: pending\n"
        "---\n"
        "# A task\n\n"
        "## Description\n"
        "What needs doing.\n"
    )
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(new), "content": missing_ac},
    })
    assert r.returncode == 2
    assert "Acceptance Criteria" in r.stderr


def test_g6_edit_removing_required_section_blocked(portfolio):
    f = portfolio / "tasks" / "t1.md"
    f.parent.mkdir(parents=True)
    f.write_text(good_doc())
    r = run_hook({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f),
                       "old_string": "## Acceptance Criteria\nDone means…\n",
                       "new_string": ""},
    })
    assert r.returncode == 2
    assert "Acceptance Criteria" in r.stderr


# ---------- G7: off-lifecycle status -----------------------------------

def test_g7_off_lifecycle_status_write_blocked(portfolio):
    new = portfolio / "tasks" / "z.md"
    new.parent.mkdir(parents=True)
    weird = good_doc().replace("status: pending", "status: 🟢 On Track")
    r = run_hook({
        "tool_name": "Write",
        "tool_input": {"file_path": str(new), "content": weird},
    })
    assert r.returncode == 2
    assert "lifecycle" in r.stderr or "Allowed values" in r.stderr


# ---------- malformed input ---------------------------------------------

def test_malformed_json_does_not_block(portfolio):
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input="this is not json",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert r.returncode == 0, r.stderr


def test_missing_file_path_does_not_block(portfolio):
    r = run_hook({"tool_name": "Edit", "tool_input": {}})
    assert r.returncode == 0, r.stderr
