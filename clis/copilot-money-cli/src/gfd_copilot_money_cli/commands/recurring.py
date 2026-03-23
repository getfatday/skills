"""Recurring command — list recurring transactions."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, render, error


@click.command()
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def recurring(fmt: str | None) -> None:
    """List recurring transactions."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_recurring, get_accounts

        items = get_recurring()
        accts = get_accounts()
        acct_map = {a.account_id: a.name for a in accts}
    except FileNotFoundError as e:
        error(str(e))

    rows = [
        {
            "name": r.name,
            "amount": f"${abs(r.amount):,.2f}",
            "frequency": r.frequency,
            "account": acct_map.get(r.account_id, ""),
        }
        for r in sorted(items, key=lambda r: r.name.lower())
    ]
    render(rows, fmt, headers=["name", "amount", "frequency", "account"])
