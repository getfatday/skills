"""Shared validator for typed-document portfolios.

Used by:
- `check-document-edit.py` — PreToolUse hook (Claude Code, plugin-side).
- `check-document-staged.py` — git pre-commit hook (materialized to a
  consuming repo's `.githooks/`).

Both scripts import this module from a sibling path, so the same logic
runs whether enforcement triggers from Claude's Edit/Write tool or from
`git commit`. The module is zero-dep (stdlib only) so it is self-
sufficient when materialized into a repo with no plugin installed.

Public API
----------
- `parse_frontmatter(text) -> (dict, body)`
- `parse_h2_sections(body) -> list[str]`
- `find_types_dir(path) -> Path | None`
- `load_type_def(types_dir, type_name) -> dict | None`
- `Violation` namedtuple (`code`, `message`)
- `check_content_integrity(types_dir, content) -> Violation | None`
- `check_line_changes(old_string, new_string) -> Violation | None`

The check functions return the **first** violation discovered or
`None` if the content is clean. Callers decide whether one violation
short-circuits, or whether to collect all (e.g., pre-commit running over
many files).
"""
from __future__ import annotations

import pathlib
import re
from typing import NamedTuple


# ---------- data ---------------------------------------------------------

class Violation(NamedTuple):
    code: str       # "G1" / "G2" / "G4" / "G5" / "G6" / "G7"
    message: str    # human-readable, ends with one or more lines of guidance


# ---------- parsing ------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter (top-level scalar `key: value` only).

    Returns (frontmatter_dict, body). If the text doesn't start with
    `---` or has no closing `---`, returns an empty dict and the
    original text. Quoted values are unquoted; nested / non-scalar lines
    are ignored.
    """
    if not text or not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end]
    fm: dict[str, str] = {}
    for line in block.splitlines():
        s = line.rstrip()
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if s[:1].isspace() or ":" not in s:
            continue
        k, _, v = s.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, text[end + 4:]


def parse_h2_sections(body: str) -> list[str]:
    """Return the list of H2 section titles, skipping fenced code blocks."""
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("## "):
            out.append(line[3:].strip())
    return out


# ---------- type-system discovery ---------------------------------------

def find_types_dir(target: pathlib.Path) -> pathlib.Path | None:
    """Walk up from `target` until `.config/documents/types/` is found.

    Returns the directory or None. Works for any path (file or
    directory; existing or planned).
    """
    start = target if target.is_absolute() else target.resolve()
    for ancestor in [start.parent, *start.parents]:
        candidate = ancestor / ".config" / "documents" / "types"
        if candidate.is_dir():
            return candidate
    return None


def load_type_def(types_dir: pathlib.Path, type_name: str) -> dict | None:
    """Read `<types_dir>/<type_name>.md` and extract required fields,
    required sections, and lifecycle values. Returns None if no such
    type definition exists.
    """
    path = types_dir / f"{type_name}.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    fields_required: list[str] = []
    sections_required: list[str] = []
    lifecycle_values: list[str] = []
    h2 = h3 = None

    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("## "):
            h2 = s[3:].strip().lower()
            h3 = None
            continue
        if s.startswith("### "):
            h3 = s[4:].strip().lower()
            continue
        if h2 == "fields" and h3 == "required" and s.startswith("- `"):
            m = re.match(r"- `([a-zA-Z0-9_-]+)\s*:", s)
            if m:
                fields_required.append(m.group(1))
        elif h2 == "sections" and h3 == "required" and s.startswith("- `## "):
            m = re.match(r"- `## ([^`]+?)`", s)
            if m:
                sections_required.append(m.group(1).strip())
        elif h2 == "lifecycle" and s.startswith("- values:"):
            lifecycle_values = [v.strip()
                                for v in s.split(":", 1)[1].split(",")
                                if v.strip()]

    return {
        "type": type_name,
        "fields_required": fields_required,
        "sections_required": sections_required,
        "lifecycle_values": lifecycle_values,
    }


# ---------- line-level guards (G1, G2) ----------------------------------

_STATUS_LINE_RE = re.compile(r"^status\s*:", re.MULTILINE)
_TYPE_LINE_RE = re.compile(r"^type\s*:\s*(\S+)", re.MULTILINE)


def check_line_changes(old_string: str, new_string: str) -> Violation | None:
    """G1/G2 — operation-discipline guards that fire on Edit-style diffs.

    G1: an Edit changes a `status:` line at all. Status transitions must
    go through the `/{type} status` operation so guards and actions run.

    G2: an Edit changes a `type:` line. Type re-classification is a
    meaningful operation (collection paths, hooks, referential
    integrity) and direct edits bypass all of it.

    Returns the first matching Violation or None.
    """
    old_string = old_string or ""
    new_string = new_string or ""

    if _STATUS_LINE_RE.search(old_string) and _STATUS_LINE_RE.search(new_string):
        return Violation("G1", (
            "Direct `status:` edits are blocked — use the update-status "
            "operation so lifecycle guards + actions run.\n"
            "  Example: /{type} status {name} {new-status}\n"
            "To add project-specific behavior to a transition, declare "
            "pre-update-status / post-update-status hooks in "
            "`.config/documents/types/{type}.skill.md` under `## Hooks`. "
            "See references/status-transitions.md and "
            "references/custom-logic-schema.md."
        ))

    m_old = _TYPE_LINE_RE.search(old_string)
    m_new = _TYPE_LINE_RE.search(new_string)
    if m_old and m_new and m_old.group(1) != m_new.group(1):
        return Violation("G2", (
            f"Direct `type:` change ({m_old.group(1)!r} → "
            f"{m_new.group(1)!r}) is blocked — type re-classification is "
            "a meaningful operation that may break collection paths and "
            "referential integrity.\n"
            "  Move the document to its new collection path and let the "
            "operation rewrite it, or delete and re-create via "
            "/{new_type} store. Both routes preserve provenance and "
            "trigger any cross-type hooks."
        ))

    return None


# ---------- content guards (G4, G5, G6, G7) -----------------------------

def check_content_integrity(types_dir: pathlib.Path,
                            content: str) -> Violation | None:
    """Run G4-G7 against the proposed file content.

    G4 — `type:` references an undefined type definition.
    G5 — at least one required field for the type is missing.
    G6 — at least one required H2 section for the type is missing.
    G7 — `status:` value is not in the type's lifecycle.

    Returns the first Violation found or None if the content is clean.
    Untyped content (no `type:`) is out of scope and returns None.
    """
    fm, body = parse_frontmatter(content)
    doc_type = fm.get("type", "").strip()
    if not doc_type:
        return None

    type_def = load_type_def(types_dir, doc_type)
    if type_def is None:
        return Violation("G4", (
            f"Type `{doc_type}` is not defined in "
            "`.config/documents/types/`. Define it before creating "
            "instances:\n"
            f"  /document:define {doc_type}\n"
            "Then use `/{type} store` or `/{type} create` to add instances."
        ))

    # G5 — missing required fields
    missing_fields = [f for f in type_def["fields_required"] if f not in fm]
    if missing_fields:
        return Violation("G5", (
            f"`{doc_type}` document is missing required field(s): "
            f"{missing_fields}.\n"
            f"  Use `/{doc_type} store` (or `/{doc_type} create`) to "
            "scaffold a complete instance. Required field set is declared "
            "under `## Fields → ### Required` in "
            f"`.config/documents/types/{doc_type}.md`."
        ))

    # G6 — missing required sections
    present_sections = parse_h2_sections(body)
    missing_sections = [s for s in type_def["sections_required"]
                        if s not in present_sections]
    if missing_sections:
        return Violation("G6", (
            f"`{doc_type}` document is missing required section(s): "
            f"{missing_sections}.\n"
            f"  Use `/{doc_type} store` (or `/{doc_type} create`) to "
            "scaffold the full section set. Required sections are "
            "declared under `## Sections → ### Required` in "
            f"`.config/documents/types/{doc_type}.md`."
        ))

    # G7 — off-lifecycle status
    if type_def["lifecycle_values"]:
        status = fm.get("status", "").strip()
        if status and status not in type_def["lifecycle_values"]:
            return Violation("G7", (
                f"`status: {status}` is not in the lifecycle for type "
                f"`{doc_type}`. Allowed values: "
                + ", ".join(type_def["lifecycle_values"]) + ".\n"
                f"  Use /{doc_type} status {{name}} <new-status> so guards "
                "and actions run. Lifecycle is declared under "
                f"`## Lifecycle` in "
                f"`.config/documents/types/{doc_type}.md`."
            ))

    return None
