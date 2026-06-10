#!/usr/bin/env python3
"""PreToolUse:Edit|Write hook for typed-document portfolios.

Reads the tool call as JSON on stdin. Computes the *proposed* file
content (the Edit applied virtually, or the Write content as given) and
runs the shared `document_validator` guards against the document's type
definition.

A blocked guard prints a reason to stderr and exits 2 — Claude sees the
message and can retry through the right lifecycle operation.

Guards (in order — first match wins):

  G1  Edit changes `status:` line          → use update-status operation
  G2  Edit changes `type:` line            → type re-classification is meaningful
  G4  Write has `type: X`, X is unknown    → run /document:define first
  G7  status: value off-lifecycle          → list valid values
  G5  resulting content missing required field
  G6  resulting content missing required H2 section
  G3  Write a new typed document directly  → use /{type} store or create

Exit codes: 0 = allow, 2 = block. Anything else is treated as allow
(non-blocking) so a bug in the hook doesn't paralyse the agent.

Guard logic lives in `document_validator.py` (sibling file) so the
same checks run in the git pre-commit (`check-document-staged.py`)
without code duplication.
"""
from __future__ import annotations

import json
import pathlib
import sys

# Sibling import — both this script and its library live in `scripts/`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from document_validator import (  # noqa: E402
    check_content_integrity,
    check_line_changes,
    find_types_dir,
    parse_frontmatter,
)


def block(message: str) -> None:
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


def proposed_content_for_edit(file_path: pathlib.Path,
                               tool_input: dict) -> str | None:
    """Apply the Edit virtually to compute the resulting file content.

    Returns None if the file doesn't exist or the substitution would
    produce no change (which is harmless either way)."""
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
    types_dir = find_types_dir(file_path)
    if types_dir is None:
        return 0  # not inside a typed-document portfolio

    # G1 / G2 — Edit-only line-level guards
    if tool_name == "Edit":
        violation = check_line_changes(
            tool_input.get("old_string", "") or "",
            tool_input.get("new_string", "") or "",
        )
        if violation is not None:
            block(violation.message)

    # Compute proposed content
    if tool_name == "Write":
        proposed = tool_input.get("content") or ""
        is_new_file = not file_path.exists()
    else:
        proposed = proposed_content_for_edit(file_path, tool_input)
        if proposed is None:
            return 0  # Edit had no effect, or target missing — let the
                       # tool surface that error itself
        is_new_file = False

    # G4 / G5 / G6 / G7 — content integrity
    violation = check_content_integrity(types_dir, proposed)
    if violation is not None:
        # G4 (unknown type) fires only on Write — for an Edit on a doc
        # whose type-def has been deleted out from under it, there's no
        # useful operation to redirect to, so we allow.
        if not (violation.code == "G4" and tool_name == "Edit"):
            block(violation.message)

    # G3 — Write a new typed document
    if tool_name == "Write" and is_new_file:
        fm, _ = parse_frontmatter(proposed)
        doc_type = fm.get("type", "").strip()
        if doc_type:
            block(
                f"Writing a new `{doc_type}` document directly bypasses "
                "the type's create operation, which sets provenance, "
                "enforces collection-path rules, and runs any declared "
                "pre-create/post-create hooks.\n"
                f"  Use:  /{doc_type} store {file_path.name}\n"
                f"    or: /{doc_type} create\n"
                "If you genuinely need a raw write (recovery, "
                "automation), declare it in "
                f"`.config/documents/types/{doc_type}.skill.md` and use "
                "the `force-raw-write` operation."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
