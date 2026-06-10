#!/usr/bin/env python3
"""Read the document-plugin target configuration.

The configured cross-IDE targets for a typed-document portfolio live
under `.config/documents/rulesync.jsonc`, alongside (but distinct from)
any repo-root `rulesync.jsonc` the consumer keeps for non-document
content. A `documentTargets: true` marker in the document config
prevents accidental cross-reads.

Public API:
- `DEFAULT_CONFIG` — the dict written into a fresh repo's config
- `parse_jsonc(text)` — JSONC → dict (strips `//` and `/* */` comments
   and tolerates trailing commas)
- `load_target_config(config_path)` — returns a parsed dict or, when
   the file is absent, the defaults. Raises `TargetConfigError` on
   malformed content or on a non-document-marker mismatch.
- `parsed_targets(config)` — flatten the targets section into the
   list `multi_target_emit.run_rulesync()` consumes.

Zero-dep — stdlib only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

__version__ = "0.1.0"


# Schema version of the rulesync.jsonc format the plugin understands.
# Bumping requires a migration step in
# `skills/document-define/references/schema-migrations.md`.
CONFIG_SCHEMA_VERSION = 1

DEFAULT_CONFIG: dict[str, Any] = {
    "documentTargets": True,
    "schema-version": CONFIG_SCHEMA_VERSION,
    "targets": {
        "cursor": ["skills", "commands", "subagents", "hooks"],
        "codexcli": ["skills", "commands"],
    },
    "delete": False,
}


class TargetConfigError(Exception):
    """Raised when the config file is present but cannot be used as
    the document-plugin's target config."""


# ---------- JSONC parsing -----------------------------------------------

# Strip `//` line comments and `/* ... */` block comments, then strip
# trailing commas inside arrays and objects. Implemented with regex
# rather than a third-party jsonc library so the reader stays stdlib-only.

_LINE_COMMENT_RE = re.compile(r"(?<![\":\\])//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def parse_jsonc(text: str) -> Any:
    """Parse JSON-with-comments. Comments and trailing commas are
    stripped before delegating to `json.loads`. Strings containing
    `//` or `/* */` literally are preserved (the regex won't match
    inside a string because it backs away from `:` and `"`)."""
    # Mask string literals so comment-stripping leaves them alone.
    string_re = re.compile(r'"(?:[^"\\]|\\.)*"')
    masks: list[str] = []

    def _mask(match: re.Match) -> str:
        masks.append(match.group(0))
        return f"\x00{len(masks) - 1}\x00"

    masked = string_re.sub(_mask, text)
    stripped = _BLOCK_COMMENT_RE.sub("", masked)
    stripped = re.sub(r"//[^\n]*", "", stripped)
    stripped = _TRAILING_COMMA_RE.sub(r"\1", stripped)

    def _unmask(match: re.Match) -> str:
        return masks[int(match.group(1))]

    restored = re.sub(r"\x00(\d+)\x00", _unmask, stripped)
    return json.loads(restored)


# ---------- config loader -----------------------------------------------

def load_target_config(config_path: pathlib.Path | str | None) -> dict[str, Any]:
    """Load the target config at `config_path`. Returns `DEFAULT_CONFIG`
    when the path is None or doesn't exist. Raises `TargetConfigError`
    when the file is present but invalid (malformed JSONC, missing the
    `documentTargets` marker, or schema-version newer than the reader)."""
    if config_path is None:
        return _copy_defaults()
    path = pathlib.Path(config_path)
    if not path.is_file():
        return _copy_defaults()

    try:
        data = parse_jsonc(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TargetConfigError(
            f"{path}: invalid JSONC ({exc.msg} at line {exc.lineno})"
        ) from exc

    if not isinstance(data, dict):
        raise TargetConfigError(f"{path}: top-level must be an object")

    if not data.get("documentTargets") is True:
        raise TargetConfigError(
            f"{path}: missing `documentTargets: true` marker — this "
            "file is not the document-plugin's target config. Either "
            "add the marker, or move the document-plugin targets to "
            "`.config/documents/rulesync.jsonc`."
        )

    schema_version = data.get("schema-version", 1)
    if not isinstance(schema_version, int) or schema_version < 1:
        raise TargetConfigError(
            f"{path}: schema-version must be an integer ≥ 1"
        )
    if schema_version > CONFIG_SCHEMA_VERSION:
        # Forward-compatible posture: warn but proceed.
        sys.stderr.write(
            f"warning: {path} schema-version is {schema_version}; "
            f"this reader supports up to {CONFIG_SCHEMA_VERSION}. "
            "Proceeding with best-effort parse.\n"
        )

    targets = data.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise TargetConfigError(
            f"{path}: `targets` must be a non-empty object mapping "
            "target name → feature list"
        )
    for name, features in targets.items():
        if not isinstance(features, list) or not all(
            isinstance(f, str) for f in features
        ):
            raise TargetConfigError(
                f"{path}: targets.{name} must be a list of feature strings"
            )

    return data


def _copy_defaults() -> dict[str, Any]:
    """Return a deep-enough copy of DEFAULT_CONFIG that callers can
    mutate without poisoning the module-level constant."""
    return {
        "documentTargets": True,
        "schema-version": DEFAULT_CONFIG["schema-version"],
        "targets": {k: list(v) for k, v in DEFAULT_CONFIG["targets"].items()},
        "delete": DEFAULT_CONFIG["delete"],
    }


# ---------- target-list flattener ---------------------------------------

def parsed_targets(config: dict[str, Any]) -> list[str]:
    """Return the configured target names in stable order — the order
    a `--targets cursor,codexcli` invocation of rulesync expects."""
    return sorted(config.get("targets", {}).keys())


def parsed_features(config: dict[str, Any]) -> list[str]:
    """Return the union of features across all configured targets, in
    stable order. Driving rulesync with the union is fine — rulesync
    skips any (target, feature) pair the target doesn't support."""
    out: set[str] = set()
    for features in config.get("targets", {}).values():
        out.update(features)
    return sorted(out)


# ---------- locator ------------------------------------------------------

def config_path_for(repo_root: pathlib.Path | str) -> pathlib.Path:
    """Canonical path of the document-plugin target config under a
    consuming repo."""
    return pathlib.Path(repo_root) / ".config" / "documents" / "rulesync.jsonc"


# ---------- CLI ----------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="target_config.py",
        description=(
            "Read .config/documents/rulesync.jsonc and print the parsed "
            "config as JSON. Used by /document:upgrade to discover the "
            "configured cross-IDE targets."
        ),
    )
    parser.add_argument("--version", action="version",
                        version=f"target_config.py {__version__}")
    parser.add_argument("-C", "--repo", default=".",
                        help="repo root (default: current directory)")
    parser.add_argument("--defaults", action="store_true",
                        help="print the default config instead of reading "
                             "the repo's file")
    args = parser.parse_args(argv)

    if args.defaults:
        json.dump(DEFAULT_CONFIG, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    path = config_path_for(args.repo)
    try:
        config = load_target_config(path)
    except TargetConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    json.dump(
        {"path": str(path), "exists": path.is_file(), "config": config,
         "targets": parsed_targets(config),
         "features": parsed_features(config)},
        sys.stdout, indent=2, sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
