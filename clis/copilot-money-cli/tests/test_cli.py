"""CLI smoke tests and E2E tests against the real Copilot Money cache."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest
from click.testing import CliRunner

from gfd_copilot_money_cli.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _resolve_cli(name: str) -> list[str]:
    """Resolve the CLI command, falling back to uv run if not installed."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    # fallback to uv run
    print(f"[_resolve_cli] Falling back to: uv run {name}")
    return ["uv", "run", name]


# ---------------------------------------------------------------------------
# Smoke tests — help and version
# ---------------------------------------------------------------------------

class TestCLISmoke:
    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Copilot Money" in result.output

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_status_help(self):
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_accounts_help(self):
        result = runner.invoke(cli, ["accounts", "--help"])
        assert result.exit_code == 0

    def test_transactions_help(self):
        result = runner.invoke(cli, ["transactions", "--help"])
        assert result.exit_code == 0

    def test_categories_help(self):
        result = runner.invoke(cli, ["categories", "--help"])
        assert result.exit_code == 0

    def test_budgets_help(self):
        result = runner.invoke(cli, ["budgets", "--help"])
        assert result.exit_code == 0

    def test_recurring_help(self):
        result = runner.invoke(cli, ["recurring", "--help"])
        assert result.exit_code == 0

    def test_summary_help(self):
        result = runner.invoke(cli, ["summary", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# E2E tests — real cache, CliRunner
# ---------------------------------------------------------------------------

class TestCLIE2E:
    """End-to-end tests that read the real Copilot Money LevelDB cache.

    These have a HARD dependency on the cache existing locally.
    No mocking, no graceful degradation.
    """

    def test_status_json(self):
        result = runner.invoke(cli, ["status", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_documents" in data

    def test_accounts_json(self):
        result = runner.invoke(cli, ["accounts", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_transactions_json(self):
        result = runner.invoke(cli, ["transactions", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_transactions_filtered(self):
        result = runner.invoke(cli, ["transactions", "--start", "2026-03-01", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_categories_json(self):
        result = runner.invoke(cli, ["categories", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_categories_flat(self):
        result = runner.invoke(cli, ["categories", "--flat", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_summary_json(self):
        result = runner.invoke(cli, ["summary", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "net_worth" in data

    def test_accounts_table(self):
        result = runner.invoke(cli, ["accounts", "--format", "table"])
        assert result.exit_code == 0, result.output
        # Table output should contain column headers
        assert "name" in result.output.lower()
        assert "balance" in result.output.lower()

    def test_transactions_csv(self):
        result = runner.invoke(cli, ["transactions", "--format", "csv"])
        assert result.exit_code == 0, result.output
        first_line = result.output.strip().split("\n")[0]
        assert "date" in first_line.lower()


# ---------------------------------------------------------------------------
# E2E tests — subprocess (installed entry point)
# ---------------------------------------------------------------------------

class TestCLISubprocess:
    """Subprocess-based E2E tests validating the installed CLI entry point."""

    CLI_BASE = _resolve_cli("gfd-copilot-money")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_subprocess_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Copilot Money" in result.stdout

    def test_subprocess_status_json(self):
        result = self._run(["status", "--format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_documents" in data

    def test_subprocess_accounts_json(self):
        result = self._run(["accounts", "--format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
