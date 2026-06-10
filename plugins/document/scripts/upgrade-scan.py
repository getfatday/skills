#!/usr/bin/env python3
"""upgrade-scan.py — scan a repository for document-plugin materialized
artifacts and classify each against the installed plugin's versions.

Tier-1 plugin-only helper for `/document:upgrade`. The skill consumes the
JSON this emits and drives regeneration, hand-edit confirmation, migration,
and re-materialization. All scanning, parsing, version comparison, and
type-def-hash comparison is done here, deterministically — so the upgrade
mechanics are testable with Layer-1 pytest while the skill handles the
judgment loop (presenting the plan, confirming hand-edits).

Zero third-party dependencies. Python 3 stdlib only.

    python3 upgrade-scan.py [-C <repo>] [--installed-plugin-root <path>]

Default repo is the current directory. Default installed-plugin-root is the
directory two levels up from this script (i.e. its own plugin) — so the
skill rarely needs to override it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

__version__ = "0.1.0"

# Sentinels delimiting the provenance header in a materialized script.
PROVENANCE_OPEN = "# --- document:provenance ---"
PROVENANCE_CLOSE = "# --- end provenance ---"

# Directories never scanned for materialized artifacts.
EXCLUDED_DIRS = {".git", ".venv", "node_modules", ".cursor", ".github",
                 ".cursor-plugin", "plugins"}

# Required fields on a Tier 2-materialized / Tier 3 skill or command stamp.
# `type-definition` and `type-definition-hash` are Tier-3 only.
REQUIRED_STAMP_FIELDS = (
    "factory", "factory-version", "generated-by",
    "generator-version", "source", "materialized", "tier",
)


# --------------------------------------------------------------------------
# version comparison
# --------------------------------------------------------------------------

def _parse_version(value):
    """Parse '0.8.0' or '1.4' into a comparable tuple of ints. Returns
    None for unparseable input — caller treats as 'unknown'."""
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _cmp_version(a, b):
    """Return -1 / 0 / +1 comparing two version strings; None if either
    side is unparseable so the caller can treat the comparison as unknown.

    Pads the shorter tuple with zeros so `"0.9"` and `"0.9.0"` compare equal
    — otherwise a stamp recorded with one component count could falsely
    flag as `ahead`/`stale` against an installed plugin using a different
    count, and `/document:upgrade` would total-refuse the run.
    """
    pa, pb = _parse_version(a), _parse_version(b)
    if pa is None or pb is None:
        return None
    length = max(len(pa), len(pb))
    pa = pa + (0,) * (length - len(pa))
    pb = pb + (0,) * (length - len(pb))
    return (pa > pb) - (pa < pb)


# --------------------------------------------------------------------------
# provenance parsers — three serializations of the same stamp
# --------------------------------------------------------------------------

def parse_skill_frontmatter(text):
    """Parse the YAML frontmatter of a SKILL.md or command markdown file.
    Returns a dict of scalar fields (the provenance stamp), or {} when
    there is no factory-stamped frontmatter."""
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
            continue  # blank, indented, or non-key line
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        fields[key.strip()] = value
    return fields if fields.get("factory") == "document" else {}


def parse_script_provenance(text):
    """Parse the `# --- document:provenance ---` header block of a
    materialized Python script. Returns a dict of scalar fields, or {} when
    there is no provenance block."""
    if not text:
        return {}
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == PROVENANCE_OPEN)
        end = next(i for i, ln in enumerate(lines[start + 1:], start + 1)
                   if ln.strip() == PROVENANCE_CLOSE)
    except StopIteration:
        return {}
    fields = {}
    for ln in lines[start + 1:end]:
        stripped = ln.strip()
        if not stripped.startswith("#"):
            continue
        body = stripped[1:].strip()
        if ":" not in body:
            continue
        key, _, value = body.partition(":")
        fields[key.strip()] = value.strip()
    return fields if fields.get("factory") == "document" else {}


def parse_config_schema_version(text):
    """Read the `schema-version:` value from a `root.md` or type-definition
    markdown file. Returns an int, or None if the line is absent (interpret
    None as version 1 per FACTORY.md)."""
    if not text:
        return None
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*schema-version\s*:\s*([0-9]+)\s*$", line)
        if m:
            return int(m.group(1))
    return None


# --------------------------------------------------------------------------
# installed plugin — read the versions the plugin advertises
# --------------------------------------------------------------------------

def read_installed_versions(plugin_root):
    """Return {factory-version, generator-version, document-schema-version}
    for the installed plugin at `plugin_root`."""
    plugin_json = json.loads(
        (plugin_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    factory_version = plugin_json.get("version", "")
    document_schema_version = int(plugin_json.get("documentSchemaVersion", 1))

    # generator-version lives inside document-define's generated-frontmatter
    # template — the first `generator-version: "X"` line in its SKILL.md.
    define_spec = (plugin_root / "skills/document-define/SKILL.md").read_text(
        encoding="utf-8"
    )
    m = re.search(r'generator-version:\s*"([^"]+)"', define_spec)
    generator_version = m.group(1) if m else ""

    return {
        "factory-version": factory_version,
        "generator-version": generator_version,
        "document-schema-version": document_schema_version,
    }


# --------------------------------------------------------------------------
# discovery — walk the repo for materialized artifacts
# --------------------------------------------------------------------------

def _iter_files(repo_root, scope_globs):
    """Yield paths under `repo_root` matching any of `scope_globs`, skipping
    EXCLUDED_DIRS at any level. Determinism: paths are yielded sorted."""
    yielded = set()
    for pattern in scope_globs:
        for path in sorted(repo_root.glob(pattern)):
            if path in yielded:
                continue
            if any(part in EXCLUDED_DIRS for part in path.relative_to(repo_root).parts):
                continue
            if path.is_file():
                yielded.add(path)
                yield path


def discover_artifacts(repo_root):
    """Walk the repo for every materialized artifact. Returns a list of
    (kind, path, text) triples. kind ∈ {skill, command, script, config}."""
    artifacts = []

    # Skills and commands materialized into the consuming repo.
    for path in _iter_files(repo_root, [".claude/skills/*/SKILL.md"]):
        artifacts.append(("skill", path, path.read_text(encoding="utf-8")))
    for path in _iter_files(repo_root, [".claude/commands/*.md"]):
        artifacts.append(("command", path, path.read_text(encoding="utf-8")))

    # Materialized scripts colocated under a materialized skill.
    for path in _iter_files(repo_root, [".claude/skills/*/scripts/*.py"]):
        artifacts.append(("script", path, path.read_text(encoding="utf-8")))

    # Config files (root.md + type definitions).
    config_dir = repo_root / ".config/documents"
    if (config_dir / "root.md").is_file():
        artifacts.append(
            ("config", config_dir / "root.md",
             (config_dir / "root.md").read_text(encoding="utf-8"))
        )
    if (config_dir / "types").is_dir():
        for path in sorted((config_dir / "types").glob("*.md")):
            if path.name.endswith(".skill.md"):
                continue  # sidecars are not type definitions
            artifacts.append(("config", path, path.read_text(encoding="utf-8")))

    return artifacts


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def _stamp_provenance(kind, text):
    """Extract the provenance dict for an artifact, or {} if absent."""
    if kind in ("skill", "command"):
        return parse_skill_frontmatter(text)
    if kind == "script":
        return parse_script_provenance(text)
    return {}


def classify_artifact(kind, path, text, repo_root, installed, plugin_root=None):
    """Return a result dict for one artifact: path, kind, provenance (or
    schema-version), classification, and human-readable reasons.

    If `plugin_root` is given, Tier-2-materialized artifacts also have their
    `source` path checked for existence inside the installed plugin and are
    classified `orphan` if the plugin removed the source template.
    """
    rel_path = str(path.relative_to(repo_root))
    result = {"path": rel_path, "kind": kind}

    if kind == "config":
        version = parse_config_schema_version(text)
        recorded = version if version is not None else 1  # absent = 1
        result["schema-version"] = recorded
        target = installed["document-schema-version"]
        if recorded > target:
            result["classification"] = "ahead"
            result["reasons"] = [
                f"schema-version: {recorded} > installed {target}"
            ]
        elif recorded < target:
            result["classification"] = "migration-needed"
            result["reasons"] = [
                f"schema-version: {recorded} -> {target}"
            ]
        else:
            result["classification"] = "current"
            result["reasons"] = []
        return result

    # Skill / command / script: provenance-stamped artifact.
    stamp = _stamp_provenance(kind, text)
    if not stamp:
        result["classification"] = "untracked"
        result["reasons"] = ["no document-plugin provenance stamp"]
        return result
    if stamp.get("provenance") == "detached":
        result["provenance"] = stamp
        result["classification"] = "detached"
        result["reasons"] = ["provenance: detached — opt-out, skip"]
        return result

    missing = [f for f in REQUIRED_STAMP_FIELDS if f not in stamp]
    if missing:
        result["provenance"] = stamp
        result["classification"] = "malformed"
        result["reasons"] = [f"missing stamp fields: {', '.join(missing)}"]
        return result

    result["provenance"] = stamp
    reasons = []
    classification = "current"

    # Compare factory-version against installed.
    cmp_factory = _cmp_version(stamp["factory-version"], installed["factory-version"])
    if cmp_factory is not None and cmp_factory > 0:
        result["classification"] = "ahead"
        result["reasons"] = [
            f"factory-version: {stamp['factory-version']} > "
            f"installed {installed['factory-version']}"
        ]
        return result
    if cmp_factory is not None and cmp_factory < 0:
        classification = "stale"
        reasons.append(
            f"factory-version: {stamp['factory-version']} < "
            f"installed {installed['factory-version']}"
        )

    # Compare generator-version against installed.
    cmp_gen = _cmp_version(stamp["generator-version"], installed["generator-version"])
    if cmp_gen is not None and cmp_gen > 0 and classification != "ahead":
        result["classification"] = "ahead"
        result["reasons"] = [
            f"generator-version: {stamp['generator-version']} > "
            f"installed {installed['generator-version']}"
        ]
        return result
    if cmp_gen is not None and cmp_gen < 0:
        classification = "stale"
        reasons.append(
            f"generator-version: {stamp['generator-version']} < "
            f"installed {installed['generator-version']}"
        )

    # Tier 3 only: type-definition existence + content-hash drift.
    if stamp.get("tier") == "3":
        type_def_rel = stamp.get("type-definition", "")
        if type_def_rel:
            type_def_path = repo_root / type_def_rel
            if not type_def_path.is_file():
                result["classification"] = "orphan"
                result["reasons"] = [f"type-definition missing: {type_def_rel}"]
                return result
            recorded_hash = stamp.get("type-definition-hash")
            if recorded_hash:
                current_hash = hashlib.sha256(type_def_path.read_bytes()).hexdigest()
                if current_hash != recorded_hash:
                    classification = "stale"
                    reasons.append("type-definition-hash drift")

    # Tier 2-materialized: orphan if the plugin removed its source template.
    if stamp.get("tier") == "2-materialized" and plugin_root is not None:
        source_rel = stamp.get("source", "")
        if source_rel and not (plugin_root / source_rel).is_file():
            result["classification"] = "orphan"
            result["reasons"] = [f"source missing in installed plugin: {source_rel}"]
            return result

    result["classification"] = classification
    result["reasons"] = reasons
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def list_available_templates(plugin_root, repo_root):
    """Yield one entry per plugin template that has no materialized form in
    `repo_root` yet. Classified `available` so `/document:upgrade` can offer
    to install them in the same pass as stale/migration/hand-edit work —
    without a separate `materialize` subcommand."""
    templates_dir = plugin_root / "templates"
    if not templates_dir.is_dir():
        return []
    available = []
    for template_dir in sorted(templates_dir.iterdir()):
        if not template_dir.is_dir() or not (template_dir / "SKILL.md").is_file():
            continue
        if (repo_root / ".claude/skills" / template_dir.name / "SKILL.md").exists():
            continue  # already materialized — handled by the artifact scan
        available.append({
            # Target path the materializer would write into this repo; every
            # artifact has a `path` so consumers can key uniformly.
            "path": f".claude/skills/{template_dir.name}/SKILL.md",
            "kind": "template",
            "template": template_dir.name,
            "classification": "available",
            "reasons": [
                f"plugin ships templates/{template_dir.name}; "
                f"not yet materialized into .claude/skills/{template_dir.name}/"
            ],
        })
    return available


def scan(repo_root, plugin_root):
    """Run the full scan + classify pass and return the result dict."""
    installed = read_installed_versions(plugin_root)
    artifacts = [
        classify_artifact(kind, path, text, repo_root, installed, plugin_root)
        for kind, path, text in discover_artifacts(repo_root)
    ]
    artifacts.extend(list_available_templates(plugin_root, repo_root))
    return {"installed": installed, "artifacts": artifacts,
            "targets": scan_targets(repo_root)}


# --------------------------------------------------------------------------
# multi-harness target configuration
# --------------------------------------------------------------------------

# Directories the materializer can produce mirrors into. Detection only —
# we never delete; that's `/document:upgrade`'s job under user
# confirmation.
KNOWN_TARGET_DIRS = {
    "cursor":     ".cursor/skills",
    "codexcli":   ".codex",
    "copilot":    ".github/skills",
    "cline":      ".cline",
    "aider":      ".aider",
    "windsurf":   ".windsurf",
    "geminicli":  ".gemini",
    "kilocode":   ".kilocode",
    "opencode":   ".opencode",
    "qwencode":   ".qwencode",
    "roo":        ".roo",
    "augmentcode": ".augment",
}


def scan_targets(repo_root):
    """Return the target-configuration state of the repo.

    {
      "config_path": ".config/documents/rulesync.jsonc",
      "config_exists": bool,
      "configured":   ["cursor", "codexcli"],
      "detected":     ["copilot"],         # output dirs present on disk
      "unconfigured": ["copilot"],         # detected ∖ configured
    }
    """
    # Local import — target_config is a sibling module. Importing at
    # call time avoids a hard cycle if upgrade-scan is loaded from a
    # location target_config can't see.
    here = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    try:
        import target_config as tc  # type: ignore
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    config_path = tc.config_path_for(repo_root)
    config_exists = config_path.is_file()
    try:
        config = tc.load_target_config(config_path)
        config_error: str | None = None
    except tc.TargetConfigError as exc:
        config = tc.load_target_config(None)  # fall back to defaults
        config_error = str(exc)
    configured = tc.parsed_targets(config)

    repo = pathlib.Path(repo_root)
    detected = []
    for name, rel_dir in KNOWN_TARGET_DIRS.items():
        if (repo / rel_dir).is_dir():
            detected.append(name)

    return {
        "config_path": str(config_path.relative_to(repo)),
        "config_exists": config_exists,
        "config_error": config_error,
        "configured": configured,
        "detected": sorted(detected),
        "unconfigured": sorted(set(detected) - set(configured)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="upgrade-scan.py",
        description=("Scan a repo for document-plugin materialized artifacts "
                     "and classify each against the installed plugin."),
    )
    parser.add_argument("--version", action="version",
                        version=f"upgrade-scan.py {__version__}")
    parser.add_argument("-C", "--repo", default=".",
                        help="repository to scan (default: current directory)")
    parser.add_argument(
        "--installed-plugin-root",
        default=str(pathlib.Path(__file__).resolve().parents[1]),
        help="path to the installed document plugin (default: this script's plugin)",
    )
    args = parser.parse_args(argv)

    repo_root = pathlib.Path(args.repo).resolve()
    plugin_root = pathlib.Path(args.installed_plugin_root).resolve()

    if not (plugin_root / ".claude-plugin/plugin.json").is_file():
        print(f"error: no plugin.json at {plugin_root}/.claude-plugin/", file=sys.stderr)
        return 1

    result = scan(repo_root, plugin_root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
