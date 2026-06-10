"""Multi-harness cross-IDE emit.

Two concerns:

1. **Stage canonical Claude Code skill+command content into a
   `.rulesync/` tree** so rulesync (and any future tool that consumes
   the same layout) has the inputs it needs.
2. **Invoke `npx -y rulesync generate …`** to fan out the staged
   content to all configured targets. Graceful: when `npx` (or
   rulesync itself) isn't available, returns a structured "deferred"
   result instead of raising — `/document:upgrade` reads that result
   and falls back to its AI-driven path (see
   `skills/document-upgrade/references/target-formats.md`).

Why this is a separate module: materialize.py shouldn't need to know
how rulesync's CLI flags work, and the AI fallback path in the
upgrade skill shouldn't need to know how staging works. Each side
talks through `stage_into_rulesync()` and `run_rulesync()` only.

Zero-dep — stdlib only.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
from typing import Any, NamedTuple


__version__ = "0.1.0"


# ---------- staging ------------------------------------------------------

def stage_into_rulesync(repo_root: pathlib.Path | str, name: str,
                         skill_text: str, command_text: str | None = None,
                         scripts: dict[str, str] | None = None,
                         evals: dict[str, str] | None = None) -> list[str]:
    """Stage one materialized skill into `.rulesync/skills/<name>/` and
    its command into `.rulesync/commands/<name>.md`.

    Important: this function operates ONLY inside its own namespace
    (`.rulesync/skills/<name>/`, `.rulesync/commands/<name>.md`). It
    never touches sibling subagents/, hooks/, rules/, mcp.json — the
    consumer's existing rulesync content is preserved verbatim.

    Returns the list of paths written (repo-relative).
    """
    repo = pathlib.Path(repo_root)
    written: list[str] = []

    skill_dir = repo / ".rulesync" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")
    written.append(str(skill_path.relative_to(repo)))

    if scripts:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for fname, body in scripts.items():
            p = scripts_dir / fname
            p.write_text(body, encoding="utf-8")
            written.append(str(p.relative_to(repo)))

    if evals:
        evals_dir = skill_dir / "evals"
        evals_dir.mkdir(parents=True, exist_ok=True)
        for fname, body in evals.items():
            p = evals_dir / fname
            p.write_text(body, encoding="utf-8")
            written.append(str(p.relative_to(repo)))

    if command_text:
        cmd_dir = repo / ".rulesync" / "commands"
        cmd_dir.mkdir(parents=True, exist_ok=True)
        cmd_path = cmd_dir / f"{name}.md"
        cmd_path.write_text(command_text, encoding="utf-8")
        written.append(str(cmd_path.relative_to(repo)))

    return written


# ---------- rulesync invocation -----------------------------------------

class RulesyncResult(NamedTuple):
    status: str          # "ok" / "deferred" / "failed"
    reason: str          # short human-readable; "" on ok
    targets: list[str]   # targets requested
    stdout: str
    stderr: str
    returncode: int


def npx_available() -> bool:
    """True when `npx` is on PATH."""
    return shutil.which("npx") is not None


def run_rulesync(repo_root: pathlib.Path | str, targets: list[str],
                 features: list[str], *, simulate: bool = True,
                 timeout: int = 180) -> RulesyncResult:
    """Invoke `npx -y rulesync generate …` from `repo_root`.

    `simulate=True` (default) passes `--simulate-skills --simulate-commands`
    so rulesync produces skill/command files for targets that don't
    natively support them (copilot/cursor/codexcli need this flag for
    skills; others don't, but rulesync ignores it where it doesn't
    apply).

    Returns a `RulesyncResult` instead of raising:

    - `status=ok` — rulesync ran and exited 0; outputs are on disk.
    - `status=deferred` — `npx` is missing. Caller should fall back to
      the AI path documented in
      `skills/document-upgrade/references/target-formats.md`.
    - `status=failed` — rulesync ran but exited non-zero. Stderr is
      captured; caller decides whether to surface or fall back.

    Idempotent: re-running with the same staged content produces the
    same outputs (rulesync's default mode is non-destructive — only
    `--delete` removes existing files).
    """
    repo = pathlib.Path(repo_root)
    targets = list(targets)

    if not npx_available():
        return RulesyncResult(
            status="deferred",
            reason=("`npx` not found on PATH — Node.js + npm install "
                    "the cross-IDE generation tool. Falling back to the "
                    "AI-driven path (see "
                    "skills/document-upgrade/references/target-formats.md)."),
            targets=targets, stdout="", stderr="", returncode=-1,
        )

    if not targets:
        return RulesyncResult(
            status="ok", reason="no targets configured",
            targets=[], stdout="", stderr="", returncode=0,
        )

    cmd = ["npx", "-y", "rulesync", "generate",
           "--targets", ",".join(targets),
           "--features", ",".join(features) if features else "skills,commands"]
    if simulate:
        cmd.extend(["--simulate-skills", "--simulate-commands"])

    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RulesyncResult(
            status="failed",
            reason=f"rulesync timed out after {timeout}s",
            targets=targets, stdout="", stderr=str(exc), returncode=-1,
        )
    except FileNotFoundError as exc:
        # npx vanished between availability check and run (race
        # condition; defensive).
        return RulesyncResult(
            status="deferred",
            reason=f"npx not invokable: {exc}",
            targets=targets, stdout="", stderr="", returncode=-1,
        )

    if proc.returncode != 0:
        return RulesyncResult(
            status="failed",
            reason=f"rulesync exited {proc.returncode}",
            targets=targets,
            stdout=proc.stdout, stderr=proc.stderr,
            returncode=proc.returncode,
        )

    return RulesyncResult(
        status="ok", reason="",
        targets=targets,
        stdout=proc.stdout, stderr=proc.stderr,
        returncode=0,
    )


def fallback_plan(repo_root: pathlib.Path | str,
                  targets: list[str]) -> dict[str, Any]:
    """Describe what the AI fallback should produce.

    Used by `/document:upgrade` when `run_rulesync()` returns deferred
    — the skill iterates over this plan and writes the files. Keeping
    the plan structured here (rather than free-form prose in the
    skill) means the same logic can be tested deterministically.
    """
    repo = pathlib.Path(repo_root)
    rulesync_skills = sorted(
        d.name for d in (repo / ".rulesync" / "skills").iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    ) if (repo / ".rulesync" / "skills").is_dir() else []
    rulesync_commands = sorted(
        f.stem for f in (repo / ".rulesync" / "commands").iterdir()
        if f.is_file() and f.suffix == ".md"
    ) if (repo / ".rulesync" / "commands").is_dir() else []
    return {
        "targets": list(targets),
        "skills": rulesync_skills,
        "commands": rulesync_commands,
        "reference": (
            "skills/document-upgrade/references/target-formats.md"
        ),
    }
