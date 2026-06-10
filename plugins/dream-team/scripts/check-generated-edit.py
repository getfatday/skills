#!/usr/bin/env python3
"""PreToolUse hook for the dream-team factory.

Reads the Claude Code tool-call payload as JSON on stdin. When the user
asks to Edit or Write a materialized dream-team artifact (per-member skill,
team skill, entry command, orchestrator agent, or any of the Cursor /
Copilot mirrors), block with a redirect to the blueprint plus the right
lifecycle command (`/dream-team:update <slug>` or natural-language
`team-member-update <slug>`).

Validation logic lives in the sibling `team_member_validator.py` so the
same checks run in the materialized pre-commit hook
(`check-blueprint-staged.py`).

Exit codes:
- 0  allow
- 2  block (Claude surfaces the stderr message to the model)
- anything else is treated as allow; a broken hook should never paralyze
  the agent.

Robust against the spaces-in-path bug — the file path arrives via JSON, not
positional arguments.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from team_member_validator import (  # noqa: E402
    canonical_path_for,
    check_direct_edit,
    is_managed_path,
    parse_provenance,
)


def proposed_content_for_edit(file_path: pathlib.Path,
                               tool_input: dict) -> str | None:
    """Apply the Edit substitution virtually to compute the resulting file
    content. Returns None when the file doesn't exist or the substitution
    won't match anything."""
    try:
        current = file_path.read_text(encoding="utf-8")
    except OSError:
        return None
    old = tool_input.get("old_string", "")
    new = tool_input.get("new_string", "")
    replace_all = bool(tool_input.get("replace_all", False))
    if not old or old not in current:
        return None
    if replace_all:
        return current.replace(old, new)
    return current.replace(old, new, 1)


def _repo_root_for(file_path: pathlib.Path) -> pathlib.Path | None:
    """Walk up from `file_path` looking for `.git` (a dir in normal repos,
    a file in git worktrees — both `.exists()`). Return the containing
    repo's working tree, or None if no enclosing repo found."""
    try:
        candidate = file_path.resolve()
    except (OSError, ValueError):
        return None
    for parent in [candidate, *candidate.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _repo_relative(file_path: pathlib.Path) -> str | None:
    """Best-effort: return the path repo-rooted (drop the prefix up to and
    including the repo's working dir). Falls back to None when no git
    context is available."""
    root = _repo_root_for(file_path)
    if root is None:
        return None
    try:
        return str(file_path.resolve().relative_to(root))
    except (OSError, ValueError):
        return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed input — don't block

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path", "")
    if not raw_path or not raw_path.endswith(".md"):
        return 0

    file_path = pathlib.Path(raw_path)
    rel = _repo_relative(file_path) or raw_path

    # Fast filter: only managed locations are interesting.
    if not is_managed_path(rel):
        return 0

    # Compute proposed content.
    if tool_name == "Write":
        proposed = tool_input.get("content") or ""
    else:
        proposed = proposed_content_for_edit(file_path, tool_input)
        if proposed is None:
            return 0  # nothing to substitute — let the tool surface its error

    # Stamp lookup. Cursor and Copilot mirrors carry only `name`/`description`
    # in their frontmatter — they have no factory stamp — so we look at the
    # canonical `.claude/...` sibling instead.
    canonical_rel = canonical_path_for(rel)
    canonical_text: str | None = None
    if canonical_rel is not None:
        # Resolve the canonical file path relative to the repo root.
        repo_root = _repo_root_for(file_path)
        if repo_root is not None:
            canonical_file = repo_root / canonical_rel
            if canonical_file.is_file():
                try:
                    canonical_text = canonical_file.read_text(encoding="utf-8")
                except OSError:
                    canonical_text = None

    current_text: str | None = None
    if file_path.is_file():
        try:
            current_text = file_path.read_text(encoding="utf-8")
        except OSError:
            current_text = None

    # Block based on the canonical (or current) file's stamp. If the canonical
    # exists, prefer it — mirrors are derived from it.
    target_for_stamp = (
        canonical_text if canonical_text is not None
        else (current_text if current_text is not None else proposed)
    )
    if parse_provenance(target_for_stamp) is None:
        return 0

    violation = check_direct_edit(rel, target_for_stamp)
    if violation is None:
        return 0

    sys.stderr.write(violation.message.rstrip() + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
