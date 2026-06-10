#!/usr/bin/env python3
"""Git pre-commit hook for the dream-team factory.

Walks the staged `.md` files and blocks the commit if any of them is a
materialized dream-team artifact that's been hand-edited. Catches the
direct-shell-edit path the PreToolUse hook can't see (`vim foo.md && git
commit`), and survives plugin uninstallation when materialized into the
consumer's `.githooks/`.

When materialized via `materialize.py --githooks`, this file ships with
`team_member_validator.py` colocated in `.githooks/lib/` so the hook works
with no plugin installed.

Exit codes:
- 0  no violations OR not in a git repo / scan failed
- 1  at least one materialized file edited directly

Print to stderr. Bypass is `git commit --no-verify`, which we name
explicitly in the error so contributors who really need to bypass don't
have to guess.

Stdlib only — argparse, subprocess, pathlib.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

# Import the validator from the same directory. Layout works both for
# plugin-resident use (`plugins/dream-team/scripts/`) and for the
# materialized form (`.githooks/lib/`).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from team_member_validator import (  # noqa: E402
    canonical_path_for,
    check_direct_edit,
)


def repo_root() -> pathlib.Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired):
        return None
    return pathlib.Path(out) if out else None


def staged_markdown(root: pathlib.Path) -> list[str]:
    """Repo-relative paths of staged .md files (added or modified)."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only",
             "--diff-filter=AM", "--", "*.md"],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired):
        return []
    return [line for line in out.splitlines() if line.strip()]


def staged_content(root: pathlib.Path, rel_path: str) -> str | None:
    """Index content for a staged file."""
    try:
        return subprocess.run(
            ["git", "show", f":{rel_path}"],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--repo", type=pathlib.Path,
        help="git repo root (default: derived from git rev-parse)",
    )
    args = parser.parse_args(argv)

    root = args.repo.resolve() if args.repo else repo_root()
    if root is None:
        return 0  # not in a git repo

    files = staged_markdown(root)
    if not files:
        return 0

    failures: list[tuple[str, str]] = []  # (path, message)
    for rel in files:
        content = staged_content(root, rel)
        if content is None:
            continue
        # For Cursor / Copilot mirrors, the stamp lives on the canonical
        # Claude sibling — the mirror's frontmatter is trimmed. Look up the
        # canonical content (staged form if also staged, else working tree).
        canonical_rel = canonical_path_for(rel)
        stamp_content = content
        if canonical_rel is not None:
            canonical_text = staged_content(root, canonical_rel)
            if canonical_text is None:
                # Fall back to on-disk form when the canonical isn't staged.
                canonical_file = root / canonical_rel
                if canonical_file.is_file():
                    try:
                        canonical_text = canonical_file.read_text(
                            encoding="utf-8"
                        )
                    except OSError:
                        canonical_text = None
            if canonical_text is not None:
                stamp_content = canonical_text
        violation = check_direct_edit(rel, stamp_content)
        if violation is not None:
            failures.append((rel, violation.message))

    if not failures:
        return 0

    sep = "━" * 60
    sys.stderr.write("\n")
    sys.stderr.write(sep + "\n")
    sys.stderr.write(
        f"  dream-team blueprint integrity: {len(failures)} "
        f"materialized file{'s' if len(failures) != 1 else ''} edited directly\n"
    )
    sys.stderr.write(sep + "\n")
    for path, msg in failures:
        sys.stderr.write(f"\n  ● {path}\n")
        for line in msg.rstrip().splitlines():
            sys.stderr.write(f"    {line}\n")
    sys.stderr.write(
        "\nFix by reverting the change and editing the blueprint instead.\n"
        "If you must bypass (and you understand the materializer will\n"
        "overwrite your edit on the next /dream-team:update), use:\n"
        "  git commit --no-verify\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
