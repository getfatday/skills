#!/usr/bin/env python3
"""upgrade-scan.py — scan a repository for dream-team materialized
artifacts and classify each against the installed plugin's versions.

Tier-1 plugin-only helper for `/dream-team:update` and `/dream-team:roster`.
The skills consume the JSON this emits and drive regeneration, hand-edit
confirmation, schema migration, and re-materialization. All scanning,
parsing, version comparison, and blueprint-hash comparison happens here,
deterministically — so upgrade mechanics are testable with Layer-1 pytest
while the skills handle judgment (presenting the plan, confirming
hand-edits, calling materialize.py).

Zero third-party dependencies. Python 3 stdlib only.

    python3 upgrade-scan.py [-C <repo>] [--installed-plugin-root <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

__version__ = "0.1.0"

# Directories never scanned for materialized artifacts.
EXCLUDED_DIRS = {".git", ".venv", "node_modules", ".cursor", ".github",
                 ".cursor-plugin", "plugins"}

# Required fields on a Tier 2-materialized / Tier 3 skill, command, or agent
# stamp. blueprint / blueprint-hash are Tier-3 only and checked separately.
REQUIRED_STAMP_FIELDS = (
    "factory", "factory-version", "generated-by",
    "generator-version", "source", "materialized", "tier",
)


# --------------------------------------------------------------------------
# Version comparison
# --------------------------------------------------------------------------

def _parse_version(value):
    """Parse '0.5.0' or '1.4' into a comparable tuple of ints. Returns None
    for unparseable input — caller treats as 'unknown'."""
    if not isinstance(value, str):
        return None
    try:
        return tuple(int(p) for p in value.split("."))
    except ValueError:
        return None


def _cmp_version(a, b):
    """Return -1 / 0 / +1 comparing two version strings; None if either side
    is unparseable. Pads shorter tuples with zeros so '0.9' == '0.9.0'."""
    pa, pb = _parse_version(a), _parse_version(b)
    if pa is None or pb is None:
        return None
    length = max(len(pa), len(pb))
    pa = pa + (0,) * (length - len(pa))
    pb = pb + (0,) * (length - len(pb))
    return (pa > pb) - (pa < pb)


# --------------------------------------------------------------------------
# Frontmatter parser
# --------------------------------------------------------------------------

def parse_frontmatter(text):
    """Parse YAML frontmatter of a markdown file into a dict of scalar
    top-level fields. Returns {} when no frontmatter is present."""
    if not text:
        return {}
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line[:1].strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def parse_provenance(text):
    """Parse the provenance stamp from a SKILL.md, command, or agent file.
    Returns the stamp dict, or {} when the file isn't factory-stamped."""
    fields = parse_frontmatter(text)
    return fields if fields.get("factory") == "dream-team" else {}


def parse_config_schema_version(text):
    """Read `schema-version:` from root.md, a blueprint, or a team blueprint.
    Returns an int, or None if absent (caller treats as version 1)."""
    if not text:
        return None
    # Frontmatter form: `schema-version: 1` at top level.
    fm = parse_frontmatter(text)
    if "schema-version" in fm:
        try:
            return int(fm["schema-version"])
        except ValueError:
            pass
    # Body form: `- schema-version: 1` under ## Configuration.
    for line in text.splitlines():
        m = re.match(r"^\s*-?\s*schema-version\s*:\s*([0-9]+)\s*$", line)
        if m:
            return int(m.group(1))
    return None


# --------------------------------------------------------------------------
# Installed plugin metadata
# --------------------------------------------------------------------------

def read_installed_versions(plugin_root):
    """Return the versions the installed plugin advertises."""
    plugin_json = json.loads(
        (plugin_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    factory_version = plugin_json.get("version", "")
    schema_version = int(plugin_json.get("dreamTeamSchemaVersion", 1))

    recruit_spec = plugin_root / "skills/team-member-recruit/SKILL.md"
    if recruit_spec.is_file():
        m = re.search(
            r'generator-version:\s*"([^"]+)"',
            recruit_spec.read_text(encoding="utf-8"),
        )
        generator_version = m.group(1) if m else ""
    else:
        generator_version = ""

    return {
        "factory-version": factory_version,
        "generator-version": generator_version,
        "dream-team-schema-version": schema_version,
    }


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def _iter_files(repo_root, scope_globs):
    """Yield matching files, skipping EXCLUDED_DIRS, in deterministic order."""
    yielded = set()
    for pattern in scope_globs:
        for path in sorted(repo_root.glob(pattern)):
            if path in yielded:
                continue
            if any(part in EXCLUDED_DIRS
                   for part in path.relative_to(repo_root).parts):
                continue
            if path.is_file():
                yielded.add(path)
                yield path


def discover_artifacts(repo_root):
    """Walk repo for every materialized artifact. Returns a list of (kind,
    path, text) triples. kind ∈ {skill, command, agent, config-root,
    config-member, config-team}."""
    artifacts = []

    for path in _iter_files(repo_root, [".claude/skills/*/SKILL.md"]):
        artifacts.append(("skill", path, path.read_text(encoding="utf-8")))
    for path in _iter_files(repo_root, [".claude/commands/*.md"]):
        artifacts.append(("command", path, path.read_text(encoding="utf-8")))
    for path in _iter_files(repo_root, [".claude/agents/*.md"]):
        artifacts.append(("agent", path, path.read_text(encoding="utf-8")))

    # Config files
    root_md = repo_root / ".config/team/root.md"
    if root_md.is_file():
        artifacts.append(
            ("config-root", root_md, root_md.read_text(encoding="utf-8"))
        )
    members_dir = repo_root / ".config/team/team-members"
    if members_dir.is_dir():
        for path in sorted(members_dir.glob("*.md")):
            artifacts.append(
                ("config-member", path, path.read_text(encoding="utf-8"))
            )
    teams_dir = repo_root / ".config/team/teams"
    if teams_dir.is_dir():
        for path in sorted(teams_dir.glob("*.md")):
            artifacts.append(
                ("config-team", path, path.read_text(encoding="utf-8"))
            )

    return artifacts


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _derive_slug(kind, rel_path):
    """Derive a stable slug for the artifact from its path. Returns None for
    kinds that don't naturally carry one (entry commands, team-assemble, the
    orchestrator agent, root.md)."""
    parts = pathlib.Path(rel_path).parts
    if kind == "config-member" and parts[:3] == (".config", "team", "team-members"):
        return pathlib.Path(parts[-1]).stem
    if kind == "config-team" and parts[:3] == (".config", "team", "teams"):
        return pathlib.Path(parts[-1]).stem
    if kind == "skill" and parts[:2] == (".claude", "skills") and len(parts) >= 4:
        # .claude/skills/<slug>/SKILL.md  → <slug>
        # .claude/skills/team-<domain>/SKILL.md → team-<domain>
        return parts[2]
    return None


def classify_artifact(kind, path, text, repo_root, installed):
    """Return a result dict for one artifact: path, kind, slug (when
    derivable), provenance (or schema-version), classification, reasons
    (human-readable) and reason_codes (stable enum strings)."""
    rel_path = str(path.relative_to(repo_root))
    result = {"path": rel_path, "kind": kind}
    slug = _derive_slug(kind, rel_path)
    if slug is not None:
        result["slug"] = slug

    if kind.startswith("config-"):
        recorded = parse_config_schema_version(text)
        recorded = recorded if recorded is not None else 1
        result["schema-version"] = recorded
        target = installed["dream-team-schema-version"]
        if recorded > target:
            result["classification"] = "ahead"
            result["reasons"] = [
                f"schema-version: {recorded} > installed {target}"
            ]
            result["reason_codes"] = ["schema-version-ahead"]
        elif recorded < target:
            result["classification"] = "migration-needed"
            result["reasons"] = [f"schema-version: {recorded} -> {target}"]
            result["reason_codes"] = ["schema-version-behind"]
        else:
            result["classification"] = "current"
            result["reasons"] = []
            result["reason_codes"] = []
        return result

    # Skill, command, or agent — provenance-stamped artifact.
    stamp = parse_provenance(text)
    if not stamp:
        result["classification"] = "untracked"
        result["reasons"] = ["no dream-team provenance stamp"]
        result["reason_codes"] = ["no-provenance-stamp"]
        return result
    if stamp.get("provenance") == "detached":
        result["provenance"] = stamp
        result["classification"] = "detached"
        result["reasons"] = ["provenance: detached — opt-out, skip"]
        result["reason_codes"] = ["detached-opt-out"]
        return result

    missing = [f for f in REQUIRED_STAMP_FIELDS if f not in stamp]
    if missing:
        result["provenance"] = stamp
        result["classification"] = "malformed"
        result["reasons"] = [f"missing stamp fields: {', '.join(missing)}"]
        result["reason_codes"] = ["malformed-stamp"]
        return result

    result["provenance"] = stamp
    reasons = []
    reason_codes = []
    classification = "current"

    # Factory-version comparison.
    cmp_factory = _cmp_version(
        stamp["factory-version"], installed["factory-version"]
    )
    if cmp_factory is not None and cmp_factory > 0:
        result["classification"] = "ahead"
        result["reasons"] = [
            f"factory-version: {stamp['factory-version']} > "
            f"installed {installed['factory-version']}"
        ]
        result["reason_codes"] = ["factory-version-ahead"]
        return result
    if cmp_factory is not None and cmp_factory < 0:
        classification = "stale"
        reasons.append(
            f"factory-version: {stamp['factory-version']} -> "
            f"{installed['factory-version']}"
        )
        reason_codes.append("factory-version-drift")

    # Tier-3 blueprint check: orphan if blueprint missing, stale if hash drifted.
    if stamp.get("tier") == "3" and "blueprint" in stamp:
        blueprint_path = repo_root / stamp["blueprint"]
        if not blueprint_path.is_file():
            result["classification"] = "orphan"
            result["reasons"] = [f"blueprint missing: {stamp['blueprint']}"]
            result["reason_codes"] = ["blueprint-missing"]
            return result
        recorded_hash = stamp.get("blueprint-hash", "")
        current_hash = _sha256(
            blueprint_path.read_text(encoding="utf-8")
        )
        if recorded_hash and recorded_hash != current_hash:
            classification = "stale"
            reasons.append(
                f"blueprint-hash drift: blueprint edited since materialization"
            )
            reason_codes.append("blueprint-hash-drift")

    # Mirror existence check (Phase 5): Claude is the canonical tree, but
    # the materializer also emits .cursor/ and .github/ mirrors. A missing
    # mirror means the user deleted (or never installed) the harness-specific
    # copy — re-materializing is a one-step fix.
    if kind == "skill":
        rel_parts = pathlib.Path(rel_path).parts
        if rel_parts[:2] == (".claude", "skills") and len(rel_parts) >= 4:
            slug = rel_parts[2]
            for mirror_rel in [
                f".cursor/skills/{slug}/SKILL.md",
                f".github/skills/{slug}/SKILL.md",
            ]:
                if not (repo_root / mirror_rel).is_file():
                    if classification != "stale":
                        classification = "stale"
                    reasons.append(f"mirror missing: {mirror_rel}")
                    reason_codes.append("mirror-missing")

    result["classification"] = classification
    result["reasons"] = reasons
    result["reason_codes"] = reason_codes
    return result


# --------------------------------------------------------------------------
# Main scan
# --------------------------------------------------------------------------

def scan_repo(repo_root, plugin_root):
    """Scan the repo, return a dict ready for JSON emission with installed
    versions and one entry per artifact."""
    installed = read_installed_versions(plugin_root)
    artifacts = discover_artifacts(repo_root)
    results = [
        classify_artifact(kind, path, text, repo_root, installed)
        for kind, path, text in artifacts
    ]
    counts = {}
    for r in results:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    return {
        "installed": installed,
        "counts": counts,
        "artifacts": results,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("-C", "--repo", type=pathlib.Path,
                        default=pathlib.Path.cwd(),
                        help="consumer repo root (default: cwd)")
    parser.add_argument("--installed-plugin-root", type=pathlib.Path,
                        help="dream-team plugin root (default: this script's plugin)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    plugin_root = (
        args.installed_plugin_root
        or pathlib.Path(__file__).resolve().parent.parent
    )
    repo_root = args.repo.resolve()

    report = scan_repo(repo_root, plugin_root)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
