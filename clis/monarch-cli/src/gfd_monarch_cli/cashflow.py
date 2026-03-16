"""Cashflow commands: summary and monthly breakdown."""

from __future__ import annotations

import asyncio
import calendar
from datetime import datetime

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render, render_single


def _month_range(year: int, month: int) -> tuple[str, str]:
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@click.group("cashflow")
def cashflow() -> None:
    """View cashflow summaries."""


@cashflow.command("summary")
@click.option("--start-date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def summary(start_date: str | None, end_date: str | None, fmt: str | None) -> None:
    """Show income vs expenses for a date range (defaults to current month)."""
    fmt = detect_format(fmt)
    mm = get_client()

    kwargs: dict = {}
    if start_date and end_date:
        kwargs["start_date"] = start_date
        kwargs["end_date"] = end_date
    elif start_date or end_date:
        click.echo("Error: both --start-date and --end-date are required together.", err=True)
        raise SystemExit(2)

    result = asyncio.run(mm.get_cashflow_summary(**kwargs))
    raw = result.get("summary", {})
    s = raw[0].get("summary", {}) if isinstance(raw, list) else raw.get("summary", {})

    data = {
        "income": f"${s.get('sumIncome', 0):,.2f}",
        "expenses": f"${s.get('sumExpense', 0):,.2f}",
        "savings": f"${s.get('savings', 0):,.2f}",
        "savings_rate": f"{(s.get('savingsRate', 0) or 0) * 100:.1f}%",
    }

    render_single(data, fmt)


@cashflow.command("monthly")
@click.option("--months", default=6, help="Number of months to show")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def monthly(months: int, fmt: str | None) -> None:
    """Show month-by-month cashflow breakdown."""
    fmt = detect_format(fmt)
    mm = get_client()

    now = datetime.now()
    rows = []

    for i in range(months - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1

        start, end = _month_range(year, month)
        result = asyncio.run(mm.get_cashflow_summary(start_date=start, end_date=end))
        raw = result.get("summary", {})
        s = raw[0].get("summary", {}) if isinstance(raw, list) else raw.get("summary", {})

        rows.append({
            "month": f"{year}-{month:02d}",
            "income": f"${s.get('sumIncome', 0):,.2f}",
            "expenses": f"${s.get('sumExpense', 0):,.2f}",
            "savings": f"${s.get('savings', 0):,.2f}",
            "savings_rate": f"{(s.get('savingsRate', 0) or 0) * 100:.1f}%",
        })

    render(rows, fmt, headers=["month", "income", "expenses", "savings", "savings_rate"])
