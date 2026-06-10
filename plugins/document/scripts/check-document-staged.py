#!/usr/bin/env python3
"""Git pre-commit hook for typed-document portfolios.

Walks the staged `.md` files in the current commit, validates each
against the type system declared in `.config/documents/types/`, and
exits non-zero if any document fails an integrity guard. Catches the
direct-shell-edit path that the Claude Code PreToolUse hook can't see
(`vim foo.md && git commit`).

Guards (a subset of the seven PreToolUse guards — only the ones that
matter for structural integrity, not Claude-operation discipline):

  G4  type: X where X has no definition in .config/documents/types/
  G5  resulting content missing required field
  G6  resulting content missing required H2 section
  G7  status: value not in the type's lifecycle

G1/G2/G3 are Claude-operation-discipline checks — they don't apply
when a contributor is editing in a shell.

Exit codes: 0 = all clean, 1 = at least one document fails. Errors
during the scan (git invocation failure, malformed type definitions)
print to stderr but exit 0 so a fragile hook doesn't paralyse commits.

Zero-dep — stdlib only. Imports its sibling `document_validator.py`.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from document_validator import (  # noqa: E402
    check_content_integrity,
    find_types_dir,
)


def repo_root() -> pathlib.Path | None:
    """Resolve the current git repo's top-level. None if not in a repo."""
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
    """Return paths (relative to repo root) of staged .md files that
    are added or modified. Excludes deletions."""
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
    """Return the staged (index) content of a file at the given
    repo-relative path. None on failure (e.g., binary blob)."""
    try:
        return subprocess.run(
            ["git", "show", f":{rel_path}"],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired):
        return None


def main() -> int:
    root = repo_root()
    if root is None:
        return 0  # not in a git repo — nothing to do

    files = staged_markdown(root)
    if not files:
        return 0

    # All staged files live under the repo root, so any of them can
    # locate the types dir. Use the first as the anchor.
    types_dir = find_types_dir(root / files[0])
    if types_dir is None:
        return 0  # not a typed-document portfolio

    failures: list[tuple[str, str, str]] = []  # (path, code, message)
    for rel in files:
        content = staged_content(root, rel)
        if content is None:
            continue
        violation = check_content_integrity(types_dir, content)
        if violation is not None:
            failures.append((rel, violation.code, violation.message))

    if not failures:
        return 0

    sys.stderr.write("\n")
    sys.stderr.write(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    sys.stderr.write(
        f"  document type-integrity check failed for {len(failures)} "
        f"file{'s' if len(failures) != 1 else ''}\n"
    )
    sys.stderr.write(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for path, code, msg in failures:
        sys.stderr.write(f"\n  [{code}] {path}\n")
        for line in msg.rstrip().splitlines():
            sys.stderr.write(f"    {line}\n")
    sys.stderr.write(
        "\nFix the issues above and re-stage, or run "
        "/document-lint to clean up the portfolio.\n"
        "To bypass for a true emergency: `git commit --no-verify`.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
