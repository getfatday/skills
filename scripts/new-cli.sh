#!/usr/bin/env bash
# new-cli.sh — Generate a new CLI skeleton.
# Usage: bash scripts/new-cli.sh <name>
# Example: bash scripts/new-cli.sh example  →  clis/example-cli/

set -euo pipefail

NAME="${1:-}"

if [ -z "$NAME" ]; then
    echo "Error: CLI name is required." >&2
    echo "Usage: bash scripts/new-cli.sh <name>" >&2
    exit 1
fi

CLI_DIR="clis/${NAME}-cli"
PKG_NAME="gfd_${NAME//-/_}_cli"
CLI_CMD="gfd-${NAME}"
PROJECT_NAME="gfd-${NAME}-cli"

if [ -d "$CLI_DIR" ]; then
    echo "Error: CLI directory '$CLI_DIR' already exists." >&2
    exit 1
fi

# Create directory structure
mkdir -p "$CLI_DIR/src/$PKG_NAME"
mkdir -p "$CLI_DIR/tests"
mkdir -p "$CLI_DIR/newsfragments"

# pyproject.toml
cat > "$CLI_DIR/pyproject.toml" <<TOML
[project]
name = "$PROJECT_NAME"
version = "0.1.0"
requires-python = ">=3.12"
description = "$PROJECT_NAME personal CLI"
dependencies = [
    "click>=8.0",
]

[project.scripts]
$CLI_CMD = "$PKG_NAME.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/$PKG_NAME"]
TOML

# src/__init__.py
cat > "$CLI_DIR/src/$PKG_NAME/__init__.py" <<PYEOF
"""$PROJECT_NAME."""
PYEOF

# src/cli.py
cat > "$CLI_DIR/src/$PKG_NAME/cli.py" <<PYEOF
"""$PROJECT_NAME CLI."""
import click


@click.group()
@click.version_option()
def cli():
    """$PROJECT_NAME CLI."""


if __name__ == "__main__":
    cli()
PYEOF

# src/context.py
cat > "$CLI_DIR/src/$PKG_NAME/context.py" <<PYEOF
"""Shared CLI context: exit codes and auth helper."""
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
PYEOF

# src/output.py
cat > "$CLI_DIR/src/$PKG_NAME/output.py" <<PYEOF
"""Output contract — JSON envelope formatter with TTY detection."""

import json
import sys
from typing import Any


def is_json_mode(ctx_json_flag: bool) -> bool:
    """Return True if --json flag passed or stdout is not a TTY."""
    return ctx_json_flag or not sys.stdout.isatty()


def success(data: dict[str, Any], json_mode: bool) -> None:
    """Emit success response."""
    if json_mode:
        print(json.dumps({"ok": True, **data}))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


def error(
    code: str,
    message: str,
    json_mode: bool,
    detail: dict[str, Any] | None = None,
) -> None:
    """Emit error response."""
    if json_mode:
        payload: dict[str, Any] = {"ok": False, "error": code, "message": message}
        if detail is not None:
            payload["detail"] = detail
        print(json.dumps(payload))
    else:
        print(f"Error [{code}]: {message}", file=sys.stderr)
PYEOF

# tests/__init__.py
touch "$CLI_DIR/tests/__init__.py"

# tests/test_cli.py
cat > "$CLI_DIR/tests/test_cli.py" <<PYEOF
"""CLI smoke tests."""
from click.testing import CliRunner
from $PKG_NAME.cli import cli


def test_version():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
PYEOF

# newsfragments/.gitkeep
touch "$CLI_DIR/newsfragments/.gitkeep"

# CHANGELOG.md
cat > "$CLI_DIR/CHANGELOG.md" <<MDEOF
# Changelog
MDEOF

echo "CLI $PROJECT_NAME created at $CLI_DIR"
echo "Run 'uv sync' to install the new CLI."
