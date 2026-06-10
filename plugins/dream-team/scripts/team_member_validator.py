"""Shared validator for dream-team materialized artifacts.

Two consumers run this logic:
- `check-generated-edit.py` (PreToolUse hook, plugin-resident) blocks
  Edit/Write tool calls on materialized files.
- `check-blueprint-staged.py` (pre-commit hook) blocks `git commit` of
  the same files when a contributor edited them in a shell. The pre-commit
  script ships in two forms: plugin-resident under `scripts/` for testing,
  and materialized into `.githooks/` of the consumer repo so it survives
  plugin uninstallation.

Both consumers share the rule set defined here:

- Tier 2-materialized: `.claude/skills/team-assemble/`, the orchestrator
  agent, the four entry commands, and their Cursor / Copilot mirrors.
- Tier 3: per-member persona skills, per-team skills, and their references
  + Cursor / Copilot mirrors.

When a file matches one of these locations AND carries a dream-team
provenance stamp, direct edits are blocked with a redirect to the
blueprint + `/dream-team:update`.

Stdlib only — pathlib, re, dataclasses.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Optional


FACTORY_NAME = "dream-team"

# Materialized locations — paths the materializer writes into the consumer.
# We anchor on these so that hand-written files outside the locations are
# left alone, even if they happen to start with `factory:` for some reason.
_MANAGED_PATH_PATTERNS = [
    # Per-member / per-team skills + references (all three IDE harnesses)
    re.compile(r"^\.claude/skills/[^/]+/SKILL\.md$"),
    re.compile(r"^\.claude/skills/[^/]+/references/[^/]+\.md$"),
    re.compile(r"^\.claude/skills/team-assemble/patterns/[^/]+\.md$"),
    re.compile(r"^\.cursor/skills/[^/]+/SKILL\.md$"),
    re.compile(r"^\.cursor/skills/[^/]+/references/[^/]+\.md$"),
    re.compile(r"^\.cursor/skills/team-assemble/patterns/[^/]+\.md$"),
    re.compile(r"^\.github/skills/[^/]+/SKILL\.md$"),
    re.compile(r"^\.github/skills/[^/]+/references/[^/]+\.md$"),
    re.compile(r"^\.github/skills/team-assemble/patterns/[^/]+\.md$"),
    # Entry commands
    re.compile(r"^\.claude/commands/(consult|coach|plan|review)\.md$"),
    re.compile(r"^\.cursor/commands/(consult|coach|plan|review)\.md$"),
    re.compile(r"^\.github/prompts/(consult|coach|plan|review)\.prompt\.md$"),
    # Orchestrator agent (Claude only)
    re.compile(r"^\.claude/agents/orchestrator\.md$"),
]


@dataclass
class Violation:
    """A blocking violation. `code` is a short ID for tests and error
    messages; `message` is the human-facing redirect."""
    code: str
    message: str


def canonical_path_for(rel_path: str) -> Optional[str]:
    """Return the repo-relative `.claude/...` form of a Cursor or Copilot
    mirror path. The mirror frontmatter is intentionally stripped to
    `name`/`description` (Phase 5), so `parse_provenance` can't detect the
    factory stamp on the mirror itself — we look at the canonical sibling
    instead.

    Returns None when `rel_path` is already canonical (under `.claude/`),
    or when no mirror mapping applies."""
    norm = rel_path[2:] if rel_path.startswith("./") else rel_path
    if norm.startswith(".cursor/skills/"):
        return ".claude/skills/" + norm[len(".cursor/skills/"):]
    if norm.startswith(".cursor/commands/"):
        return ".claude/commands/" + norm[len(".cursor/commands/"):]
    if norm.startswith(".github/skills/"):
        return ".claude/skills/" + norm[len(".github/skills/"):]
    if norm.startswith(".github/prompts/") and norm.endswith(".prompt.md"):
        # `.github/prompts/consult.prompt.md` → `.claude/commands/consult.md`
        rest = norm[len(".github/prompts/"):-len(".prompt.md")]
        return f".claude/commands/{rest}.md"
    return None


def is_managed_path(rel_path: str) -> bool:
    """True iff the path is a location the materializer owns. Accepts
    either repo-relative paths (`.claude/skills/...`) or paths with a
    leading `./` (`./.claude/skills/...`)."""
    if not rel_path:
        return False
    normalized = rel_path[2:] if rel_path.startswith("./") else rel_path
    return any(p.match(normalized) for p in _MANAGED_PATH_PATTERNS)


def parse_provenance(content: str) -> Optional[dict]:
    """Return the dream-team provenance stamp as a dict, or None if the
    content has no frontmatter / no `factory: dream-team` field. Cheap
    line-by-line parse — frontmatter only.
    """
    if not content.startswith("---\n"):
        return None
    end = content.find("\n---\n", 4)
    if end < 0:
        return None
    block = content[4:end]
    fields: dict = {}
    for line in block.split("\n"):
        if ":" not in line:
            continue
        if line.startswith(" ") or line.startswith("\t") or line.startswith("-"):
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
            raw = raw[1:-1].replace("''", "'")
        elif raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
            raw = raw[1:-1]
        if raw:
            fields[key] = raw
    if fields.get("factory") != FACTORY_NAME:
        return None
    return fields


def _slug_from_path(rel_path: str) -> str:
    """Best-effort slug extraction from a managed path for the redirect
    message. Returns the empty string when no member slug applies (e.g.
    orchestrator)."""
    parts = pathlib.Path(rel_path).parts
    if len(parts) >= 3 and parts[1] in ("skills",) and parts[0] in (
        ".claude", ".cursor", ".github"
    ):
        slug = parts[2]
        # Strip the `team-` prefix from team-domain skills to recover the
        # blueprint stem (.config/team/teams/<domain>.md).
        if slug.startswith("team-") and slug != "team-assemble":
            return slug[len("team-"):]
        return slug
    if len(parts) >= 2 and parts[0] in (".claude", ".cursor") and parts[1] == "commands":
        return pathlib.Path(parts[-1]).stem
    if len(parts) >= 2 and parts[0] == ".github" and parts[1] == "prompts":
        return pathlib.Path(parts[-1]).name.replace(".prompt.md", "")
    return ""


def _blueprint_path_for(rel_path: str, slug: str) -> str:
    """The blueprint path the user should edit instead. Returns '' for
    paths with no per-slug blueprint (orchestrator, team-assemble, entry
    commands)."""
    parts = pathlib.Path(rel_path).parts
    if len(parts) >= 3 and parts[1] == "skills":
        sk = parts[2]
        if sk == "team-assemble":
            return ""  # generic workflow — no per-slug blueprint
        if sk.startswith("team-"):
            return f".config/team/teams/{slug}.md"
        return f".config/team/team-members/{slug}.md"
    return ""


def check_direct_edit(rel_path: str, content: str) -> Optional[Violation]:
    """Return a Violation when a managed file is being directly edited.
    Returns None when the file is unmanaged or has no dream-team stamp.

    `content` is the proposed (post-edit) content. We require the dream-team
    stamp to still be present — a file in a managed location without the
    stamp is treated as user-owned and allowed.
    """
    if not is_managed_path(rel_path):
        return None
    stamp = parse_provenance(content)
    if stamp is None:
        return None
    # `provenance: detached` is the user's documented opt-out — once set,
    # they own the file and the hook leaves it alone. `upgrade-scan.py`
    # treats this as `detached` classification; the hooks must too.
    if stamp.get("provenance") == "detached":
        return None

    slug = _slug_from_path(rel_path)
    blueprint = _blueprint_path_for(rel_path, slug)

    lines = [
        f"`{rel_path}` is materialized by the dream-team factory and is not "
        "meant to be edited directly.",
        "",
    ]
    if blueprint:
        lines += [
            f"  Source of truth: {blueprint}",
            "",
            "  To incorporate net-new material (a new book, talk, deeper",
            "  coverage of a topic), use natural language:",
            f'    "update {slug} with <new material>"',
            f"    → invokes `team-member-update {slug}` (research-driven enrichment).",
            "",
            "  To refresh the materialized files after editing the blueprint",
            "  by hand:",
            f"    /dream-team:update {slug}",
            "",
        ]
    else:
        lines += [
            "  This is a workflow / orchestration template — not per-slug.",
            "  To pull factory updates:",
            "    /dream-team:update",
            "",
        ]
    lines += [
        "  Or set `provenance: detached` in the frontmatter to opt out and "
        "take ownership of this file.",
    ]
    return Violation(code="DT-EDIT", message="\n".join(lines))
