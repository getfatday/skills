"""Recurring transaction commands."""

from __future__ import annotations

import asyncio

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render


@click.group("recurring")
def recurring() -> None:
    """View recurring transactions and bills."""


@recurring.command("list")
@click.option("--start-date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def list_recurring(start_date: str | None, end_date: str | None, fmt: str | None) -> None:
    """List recurring transactions/bills for the current month."""
    fmt = detect_format(fmt)
    mm = get_client()

    kwargs: dict = {}
    if start_date and end_date:
        kwargs["start_date"] = start_date
        kwargs["end_date"] = end_date
    elif start_date or end_date:
        click.echo("Error: both --start-date and --end-date are required together.", err=True)
        raise SystemExit(2)

    result = asyncio.run(mm.get_recurring_transactions(**kwargs))
    items = result.get("recurringTransactionItems", [])

    rows = []
    for item in items:
        stream = item.get("stream") or {}
        merchant = stream.get("merchant") or {}
        account = item.get("account") or {}
        category = item.get("category") or {}

        rows.append({
            "date": item.get("date", ""),
            "merchant": merchant.get("name", ""),
            "amount": f"${item.get('amount', 0):,.2f}",
            "frequency": stream.get("frequency", ""),
            "category": category.get("name", ""),
            "account": account.get("displayName", ""),
            "past": item.get("isPast", False),
        })

    headers = ["date", "merchant", "amount", "frequency", "category", "account", "past"]
    render(rows, fmt, headers=headers)
