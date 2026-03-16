"""Tests for gfd-monarch CLI structure and imports."""

from __future__ import annotations

from click.testing import CliRunner

from gfd_monarch_cli.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Personal finance CLI" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_auth_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "--help"])
    assert result.exit_code == 0
    assert "login" in result.output
    assert "logout" in result.output
    assert "status" in result.output


def test_accounts_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["accounts", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "balances" in result.output


def test_transactions_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["transactions", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "search" in result.output


def test_categories_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["categories", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "create" in result.output


def test_budgets_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["budgets", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output


def test_cashflow_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["cashflow", "--help"])
    assert result.exit_code == 0
    assert "summary" in result.output
    assert "monthly" in result.output


def test_recurring_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["recurring", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output


def test_output_module_imports():
    from gfd_monarch_cli.output import render, render_single, detect_format, error
    assert callable(render)
    assert callable(render_single)
    assert callable(detect_format)
    assert callable(error)


def test_render_json_empty():
    from io import StringIO
    from unittest.mock import patch
    from gfd_monarch_cli.output import render

    with patch("click.echo") as mock_echo:
        render([], "json")
        mock_echo.assert_called_once_with("[]")


def test_render_json_data():
    import json
    from unittest.mock import patch
    from gfd_monarch_cli.output import render

    data = [{"name": "Test", "value": 42}]
    with patch("click.echo") as mock_echo:
        render(data, "json")
        output = mock_echo.call_args[0][0]
        parsed = json.loads(output)
        assert parsed == data


def test_detect_format_explicit():
    from gfd_monarch_cli.output import detect_format
    assert detect_format("json") == "json"
    assert detect_format("csv") == "csv"
    assert detect_format("table") == "table"
