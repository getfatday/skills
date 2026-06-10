"""Layer-1 tests for multi_target_emit.py.

Covers:
- staging into `.rulesync/skills/<name>/` and `.rulesync/commands/`
- preservation of sibling `.rulesync/` content (subagents, mcp.json, …)
- `run_rulesync()` when npx is missing → deferred
- `run_rulesync()` when rulesync exits non-zero → failed
- `fallback_plan()` shape

One real end-to-end test gated on `npx` availability that drives
rulesync against a scratch repo and verifies `.cursor/` + `.codex/`
outputs.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).with_name("multi_target_emit.py")


def _load():
    spec = importlib.util.spec_from_file_location("mte_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mte = _load()


SKILL_TEXT = (
    "---\n"
    "name: document-events\n"
    "description: derive a CDC-style event log from git history\n"
    "---\n"
    "# document-events\n\n"
    "## When to Run\nRun this skill when …\n"
)

CMD_TEXT = (
    "---\n"
    "description: emit a CDC-style document change-event log\n"
    "---\n"
    "Body.\n"
)


# ---------- stage_into_rulesync ----------------------------------------

def test_stage_writes_skill_and_command(tmp_path):
    written = mte.stage_into_rulesync(
        tmp_path, "document-events", SKILL_TEXT, command_text=CMD_TEXT,
    )
    skill = tmp_path / ".rulesync/skills/document-events/SKILL.md"
    cmd = tmp_path / ".rulesync/commands/document-events.md"
    assert skill.is_file()
    assert cmd.is_file()
    assert skill.read_text() == SKILL_TEXT
    assert cmd.read_text() == CMD_TEXT
    assert ".rulesync/skills/document-events/SKILL.md" in written
    assert ".rulesync/commands/document-events.md" in written


def test_stage_with_scripts_and_evals(tmp_path):
    mte.stage_into_rulesync(
        tmp_path, "x", SKILL_TEXT, command_text=None,
        scripts={"helper.py": "# helper"},
        evals={"evals.json": '{"version": 1}'},
    )
    assert (tmp_path / ".rulesync/skills/x/scripts/helper.py").is_file()
    assert (tmp_path / ".rulesync/skills/x/evals/evals.json").is_file()


def test_stage_preserves_sibling_rulesync_content(tmp_path):
    """Re-materializing a skill must not touch sibling
    `.rulesync/subagents/`, `.rulesync/hooks/`, `.rulesync/mcp.json` —
    the consumer's hand-written rulesync content."""
    sub = tmp_path / ".rulesync/subagents"
    sub.mkdir(parents=True)
    (sub / "orchestrator.md").write_text("user-authored content")
    (tmp_path / ".rulesync/mcp.json").write_text('{"servers": {}}')

    mte.stage_into_rulesync(tmp_path, "doc-x", SKILL_TEXT, command_text=CMD_TEXT)

    assert (sub / "orchestrator.md").read_text() == "user-authored content"
    assert (tmp_path / ".rulesync/mcp.json").read_text() == '{"servers": {}}'


def test_stage_overwrites_own_namespace(tmp_path):
    """Re-staging the same name updates its own files."""
    mte.stage_into_rulesync(tmp_path, "a", SKILL_TEXT, command_text=CMD_TEXT)
    new = SKILL_TEXT.replace("derive a CDC-style event log",
                             "different description now")
    mte.stage_into_rulesync(tmp_path, "a", new, command_text=CMD_TEXT)
    assert (tmp_path / ".rulesync/skills/a/SKILL.md").read_text() == new


# ---------- run_rulesync — missing npx → deferred ----------------------

def test_run_rulesync_missing_npx_is_deferred(tmp_path, monkeypatch):
    monkeypatch.setattr(mte, "npx_available", lambda: False)
    result = mte.run_rulesync(tmp_path, ["cursor", "codexcli"],
                              ["skills", "commands"])
    assert result.status == "deferred"
    assert "npx" in result.reason.lower()
    assert result.targets == ["cursor", "codexcli"]
    assert result.returncode == -1


# ---------- run_rulesync — failures ------------------------------------

def test_run_rulesync_subprocess_failure_is_failed(tmp_path, monkeypatch):
    """rulesync exits non-zero → status=failed with the captured rc."""
    monkeypatch.setattr(mte, "npx_available", lambda: True)

    def fake_run(*args, **kwargs):
        # Return a CompletedProcess with rc=2
        class P:
            returncode = 2
            stdout = ""
            stderr = "rulesync: oops\n"
        return P()
    monkeypatch.setattr(mte.subprocess, "run", fake_run)

    result = mte.run_rulesync(tmp_path, ["cursor"], ["skills"])
    assert result.status == "failed"
    assert result.returncode == 2
    assert "oops" in result.stderr


def test_run_rulesync_timeout_is_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(mte, "npx_available", lambda: True)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["npx"], timeout=1)
    monkeypatch.setattr(mte.subprocess, "run", fake_run)

    result = mte.run_rulesync(tmp_path, ["cursor"], ["skills"], timeout=1)
    assert result.status == "failed"
    assert "timed out" in result.reason


def test_run_rulesync_no_targets_is_ok(tmp_path):
    """Empty targets list is a valid no-op, not an error."""
    result = mte.run_rulesync(tmp_path, [], ["skills"])
    assert result.status == "ok"
    assert "no targets" in result.reason


# ---------- run_rulesync — invocation shape ----------------------------

def test_run_rulesync_invokes_correct_command(tmp_path, monkeypatch):
    monkeypatch.setattr(mte, "npx_available", lambda: True)
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")

        class P:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return P()
    monkeypatch.setattr(mte.subprocess, "run", fake_run)

    mte.run_rulesync(tmp_path, ["cursor", "codexcli"],
                     ["skills", "commands"])
    cmd = captured["cmd"]
    assert cmd[:4] == ["npx", "-y", "rulesync", "generate"]
    assert "--targets" in cmd
    assert "cursor,codexcli" in cmd
    assert "--features" in cmd
    assert "skills,commands" in cmd
    # simulate flags default to on so copilot/cursor/codexcli get skills.
    assert "--simulate-skills" in cmd
    assert "--simulate-commands" in cmd
    assert str(tmp_path) == str(captured["cwd"])


# ---------- fallback_plan ----------------------------------------------

def test_fallback_plan_describes_staged_content(tmp_path):
    mte.stage_into_rulesync(tmp_path, "document-events", SKILL_TEXT,
                             command_text=CMD_TEXT)
    mte.stage_into_rulesync(tmp_path, "document-lint", SKILL_TEXT,
                             command_text=None)
    plan = mte.fallback_plan(tmp_path, ["cursor", "codexcli"])
    assert plan["targets"] == ["cursor", "codexcli"]
    assert "document-events" in plan["skills"]
    assert "document-lint" in plan["skills"]
    assert "document-events" in plan["commands"]
    assert "document-lint" not in plan["commands"]  # no command staged
    assert "target-formats.md" in plan["reference"]


def test_fallback_plan_with_empty_staging(tmp_path):
    plan = mte.fallback_plan(tmp_path, ["cursor"])
    assert plan["skills"] == []
    assert plan["commands"] == []


# ---------- the real end-to-end test ------------------------------------

@pytest.mark.skipif(shutil.which("npx") is None,
                    reason="npx not on PATH; deferred-path tests cover the rest")
def test_run_rulesync_against_real_rulesync(tmp_path):
    """Boots a scratch repo, stages a skill + command into
    `.rulesync/`, invokes real rulesync, and asserts the per-target
    outputs match what we documented in target-formats.md.

    Guards against format drift in rulesync: if rulesync changes its
    output format, this test fails noisily so we update the docs +
    AI fallback together.
    """
    mte.stage_into_rulesync(tmp_path, "document-events", SKILL_TEXT,
                             command_text=CMD_TEXT)

    result = mte.run_rulesync(
        tmp_path, ["cursor", "codexcli", "copilot"],
        ["skills", "commands"],
    )
    assert result.status == "ok", f"rulesync failed: {result.stderr}"

    cursor_skill = tmp_path / ".cursor/skills/document-events/SKILL.md"
    codex_skill = tmp_path / ".codex/skills/document-events/SKILL.md"
    copilot_skill = tmp_path / ".github/skills/document-events/SKILL.md"

    for path in (cursor_skill, codex_skill, copilot_skill):
        assert path.is_file(), f"missing {path}"
        content = path.read_text(encoding="utf-8")
        assert "name: document-events" in content
        assert "derive a CDC-style event log" in content
        # body content carried through
        assert "When to Run" in content

    # Copilot command goes to .github/prompts/<name>.prompt.md
    copilot_cmd = tmp_path / ".github/prompts/document-events.prompt.md"
    assert copilot_cmd.is_file()
    assert "description:" in copilot_cmd.read_text(encoding="utf-8")
