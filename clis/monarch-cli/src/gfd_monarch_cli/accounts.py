"""Account commands: list accounts, balances."""

from __future__ import annotations

import asyncio

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render


@click.group("accounts")
def accounts() -> None:
    """View connected accounts and balances."""


@accounts.command("list")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
@click.option("--include-hidden", is_flag=True, help="Include hidden accounts")
def list_accounts(fmt: str | None, include_hidden: bool) -> None:
    """List all connected accounts."""
    fmt = detect_format(fmt)
    mm = get_client()
    result = asyncio.run(mm.get_accounts())
    accts = result.get("accounts", [])

    if not include_hidden:
        accts = [a for a in accts if not a.get("isHidden")]

    rows = []
    for a in accts:
        rows.append({
            "id": a["id"],
            "name": a.get("displayName", ""),
            "type": a.get("type", {}).get("display", ""),
            "subtype": (a.get("subtype") or {}).get("display", ""),
            "balance": a.get("displayBalance", a.get("currentBalance", "")),
            "institution": (a.get("institution") or {}).get("name", ""),
            "updated": a.get("displayLastUpdatedAt", ""),
        })

    render(rows, fmt, headers=["id", "name", "type", "subtype", "balance", "institution", "updated"])


@accounts.command("balances")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def balances(fmt: str | None) -> None:
    """Show account balances summary."""
    fmt = detect_format(fmt)
    mm = get_client()
    result = asyncio.run(mm.get_accounts())
    accts = result.get("accounts", [])
    accts = [a for a in accts if not a.get("isHidden")]

    rows = []
    total = 0.0
    for a in accts:
        bal = a.get("displayBalance", a.get("currentBalance", 0)) or 0
        is_asset = a.get("isAsset", True)
        rows.append({
            "name": a.get("displayName", ""),
            "type": a.get("type", {}).get("display", ""),
            "balance": f"${bal:,.2f}",
            "in_net_worth": a.get("includeInNetWorth", False),
        })
        if a.get("includeInNetWorth", False):
            total += float(bal) if is_asset else -float(bal)

    rows.append({
        "name": "--- NET WORTH ---",
        "type": "",
        "balance": f"${total:,.2f}",
        "in_net_worth": "",
    })

    render(rows, fmt, headers=["name", "type", "balance", "in_net_worth"])
