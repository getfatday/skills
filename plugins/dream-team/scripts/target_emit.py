"""Target-specific emit transforms for materialized dream-team artifacts.

The factory materializes the same canonical artifact into three IDE harnesses:

- **Claude Code** — `.claude/skills|commands|agents/...`. The canonical form
  with the full provenance stamp on every artifact.
- **Cursor** — `.cursor/skills|commands/...`. Frontmatter stripped to
  `name`/`description`; the body is preserved verbatim.
- **GitHub Copilot** — `.github/skills/...` and `.github/prompts/<verb>.prompt.md`.
  Same frontmatter discipline as Cursor but the description is YAML-folded.

This module is pure transform logic — no I/O. The caller (materialize.py)
writes (path, content) pairs returned from emit_*().

Pure stdlib (re, dataclasses, textwrap). Same dependency discipline as the
rest of `scripts/`.
"""

from __future__ import annotations

import re
import textwrap
from typing import Optional, Tuple

ALL_TARGETS = ("claude", "cursor", "copilot")


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)", re.DOTALL)


def split_frontmatter(text: str) -> Tuple[dict, str, str]:
    """Return (fields, raw_frontmatter, body). fields is a flat dict of the
    top-level scalar fields the materializer cares about; nested structures
    are ignored (this module only reads `name` and `description`).
    Returns ({}, "", text) if there's no frontmatter."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, "", text
    raw = m.group(1)
    body = m.group(2)
    fields = _parse_simple_yaml_scalars(raw)
    return fields, raw, body


def _parse_simple_yaml_scalars(raw: str) -> dict:
    """Tiny scalar-only YAML parser that handles the field shapes the materializer
    emits: plain string, single-quoted, double-quoted, and folded scalars (`>-`
    followed by an indented block). Lists and nested mappings are skipped."""
    fields: dict = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip list items / nested entries — only top-level keys.
        if not line or line.startswith(" ") or line.startswith("\t") or line.startswith("-"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest in (">-", ">", "|", "|-"):
            # Folded/literal scalar — collect indented continuation.
            chunks = []
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i] == ""):
                chunks.append(lines[i].lstrip())
                i += 1
            fields[key] = " ".join(c for c in chunks if c).strip()
            continue
        if rest.startswith("'") and rest.endswith("'") and len(rest) >= 2:
            # YAML single-quoted: the escape sequence is doubled single quotes.
            fields[key] = rest[1:-1].replace("''", "'")
        elif rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
            # YAML double-quoted: backslash-escaped quotes and backslashes.
            fields[key] = (
                rest[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            )
        elif rest.startswith("[") or rest.startswith("{"):
            # Inline list/map — not consumed by emit transforms.
            pass
        elif rest == "":
            # Empty value means a block list/mapping follows on indented lines.
            # Skip — emit transforms only need scalar fields (name, description).
            pass
        else:
            fields[key] = rest
        i += 1
    return fields


# --------------------------------------------------------------------------
# Frontmatter rendering
# --------------------------------------------------------------------------

_RESERVED_INLINE = re.compile(
    r"^(true|false|null|yes|no|on|off|~|-?\d+(\.\d+)?([eE][+-]?\d+)?)$",
    re.IGNORECASE,
)


def _yaml_inline_quote(value: str) -> str:
    """Wrap a scalar in single quotes if it contains characters that would
    confuse the YAML inline form, looks like a YAML special value (booleans,
    null, numbers), or begins with a YAML structural marker. Otherwise return
    as-is."""
    if not value:
        return "''"
    needs_quote = (
        any(ch in value for ch in ":#&*!|>'\"%@`")
        or value.lstrip() != value
        or value[0] in "-?[{,"
        or value.startswith("---")
        or _RESERVED_INLINE.match(value) is not None
    )
    if needs_quote:
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return value


def _yaml_folded(value: str, indent: int = 2, width: int = 80) -> str:
    """Render a scalar as a YAML-folded (`>-`) block. Used by Copilot when
    the description is longer than ~80 chars or contains line-breaking
    characters."""
    wrapped = textwrap.fill(value, width=width - indent)
    pad = " " * indent
    body = "\n".join(pad + line for line in wrapped.split("\n"))
    return f">-\n{body}"


def _render_description(target: str, description: str) -> str:
    """Format a description value for the target's frontmatter."""
    if target == "copilot" and (len(description) > 80 or "\n" in description):
        return _yaml_folded(description)
    return _yaml_inline_quote(description)


# --------------------------------------------------------------------------
# Public API — per-artifact emit
# --------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_slug(slug: str, label: str = "slug") -> None:
    """Reject slugs / verb names / reference subpaths that could escape the
    target tree. Materialized paths interpolate the slug verbatim into
    `.claude/skills/<slug>/...` etc.; a slug like `../..` would write outside
    the consumer repo. Slugs are emitted from CLI args or marketplace JSON,
    so this is a defense-in-depth boundary check."""
    if not _SLUG_RE.match(slug or ""):
        raise ValueError(
            f"invalid {label}: {slug!r}; must match {_SLUG_RE.pattern}"
        )


def _validate_ref_subpath(subpath: str) -> None:
    """Reference subpaths look like `references/foo.md` or `patterns/bar.md`.
    Reject `..` segments and absolute paths."""
    if (
        not subpath
        or subpath.startswith("/")
        or ".." in subpath.split("/")
    ):
        raise ValueError(
            f"invalid reference subpath: {subpath!r}; must be relative and "
            "must not contain '..' segments"
        )


def _build_frontmatter(target: str, *, name: Optional[str], description: str) -> str:
    """Build the trimmed frontmatter block per target conventions."""
    lines = ["---"]
    if name:
        lines.append(f"name: {_yaml_inline_quote(name)}")
    lines.append(f"description: {_render_description(target, description)}")
    lines.append("---")
    return "\n".join(lines)


def _transform(content: str, target: str, *, keep_name: bool, fallback_name: Optional[str] = None) -> str:
    """Strip the canonical frontmatter and rebuild the target-specific one.
    Preserves the body verbatim (including any tag blocks like <objective>).
    """
    fields, _, body = split_frontmatter(content)
    description = fields.get("description", "")
    name = fields.get("name", fallback_name) if keep_name else None
    front = _build_frontmatter(target, name=name, description=description)
    return f"{front}\n{body}"


def emit_skill(target: str, content: str, slug: str) -> Tuple[str, str]:
    """Return (repo-relative output path, transformed content) for a skill."""
    _validate_slug(slug)
    if target == "claude":
        return f".claude/skills/{slug}/SKILL.md", content
    transformed = _transform(content, target, keep_name=True, fallback_name=slug)
    if target == "cursor":
        return f".cursor/skills/{slug}/SKILL.md", transformed
    if target == "copilot":
        return f".github/skills/{slug}/SKILL.md", transformed
    raise ValueError(f"unknown target: {target!r}")


def emit_command(target: str, content: str, verb: str) -> Tuple[str, str]:
    """Return (repo-relative output path, transformed content) for a command."""
    _validate_slug(verb, label="verb")
    if target == "claude":
        return f".claude/commands/{verb}.md", content
    transformed = _transform(content, target, keep_name=False)
    if target == "cursor":
        return f".cursor/commands/{verb}.md", transformed
    if target == "copilot":
        return f".github/prompts/{verb}.prompt.md", transformed
    raise ValueError(f"unknown target: {target!r}")


def emit_agent(target: str, content: str, name: str) -> Optional[Tuple[str, str]]:
    """Return (output path, content) for an agent — Claude only. Returns None
    for Cursor and Copilot, which have no agents concept."""
    _validate_slug(name, label="agent name")
    if target == "claude":
        return f".claude/agents/{name}.md", content
    if target in ("cursor", "copilot"):
        return None
    raise ValueError(f"unknown target: {target!r}")


def emit_reference(target: str, content: str, slug: str, ref_subpath: str) -> Tuple[str, str]:
    """Reference files (under references/, patterns/, etc.) mirror byte-identical
    across targets — they have no frontmatter to transform."""
    _validate_slug(slug)
    _validate_ref_subpath(ref_subpath)
    if target == "claude":
        return f".claude/skills/{slug}/{ref_subpath}", content
    if target == "cursor":
        return f".cursor/skills/{slug}/{ref_subpath}", content
    if target == "copilot":
        return f".github/skills/{slug}/{ref_subpath}", content
    raise ValueError(f"unknown target: {target!r}")
