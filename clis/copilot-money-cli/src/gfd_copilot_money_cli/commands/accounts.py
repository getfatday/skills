"""Accounts command — list accounts with balances."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, error, render


@click.command()
@click.option("--type", "account_type", default=None, help="Filter by type.")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def accounts(account_type: str | None, fmt: str | None) -> None:
    """List accounts with balances."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_accounts

        accts = get_accounts(type_filter=account_type)
    except FileNotFoundError as e:
        error(str(e))

    rows = [
        {
            "name": a.name,
            "type": a.account_type,
            "institution": a.institution_name,
            "balance": f"${abs(a.current_balance):,.2f}",
            "mask": a.mask,
        }
        for a in sorted(accts, key=lambda a: a.name.lower())
    ]
    render(rows, fmt, headers=["name", "type", "institution", "balance", "mask"])
