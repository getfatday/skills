"""Transaction commands: list, search."""

from __future__ import annotations

import asyncio

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render

HEADERS = ["date", "merchant", "category", "amount", "account", "id"]


def _format_transactions(txns: list[dict]) -> list[dict]:
    rows = []
    for t in txns:
        rows.append({
            "id": t["id"],
            "date": t.get("date", ""),
            "merchant": (t.get("merchant") or {}).get("name", t.get("plaidName", "")),
            "category": (t.get("category") or {}).get("name", ""),
            "amount": f"${t.get('amount', 0):,.2f}",
            "account": (t.get("account") or {}).get("displayName", ""),
            "pending": t.get("pending", False),
            "notes": t.get("notes", "") or "",
        })
    return rows


@click.group("transactions")
def transactions() -> None:
    """View and search transactions."""


@transactions.command("list")
@click.option("--limit", default=25, help="Number of transactions to fetch")
@click.option("--offset", default=0, help="Number of transactions to skip")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def list_transactions(limit: int, offset: int, fmt: str | None) -> None:
    """List recent transactions."""
    fmt = detect_format(fmt)
    mm = get_client()
    result = asyncio.run(mm.get_transactions(limit=limit, offset=offset))
    txns = result.get("allTransactions", {}).get("results", [])
    total = result.get("allTransactions", {}).get("totalCount", 0)

    rows = _format_transactions(txns)
    if fmt == "table":
        click.echo(f"Showing {len(rows)} of {total} transactions\n")
    render(rows, fmt, headers=HEADERS)


@transactions.command("search")
@click.option("--query", "-q", "search_query", default="", help="Search text")
@click.option("--start-date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--category", default=None, help="Category ID to filter by")
@click.option("--account", default=None, help="Account ID to filter by")
@click.option("--limit", default=50, help="Max results")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def search(
    search_query: str,
    start_date: str | None,
    end_date: str | None,
    category: str | None,
    account: str | None,
    limit: int,
    fmt: str | None,
) -> None:
    """Search transactions by date range, category, account, or text."""
    fmt = detect_format(fmt)
    mm = get_client()

    kwargs: dict = {"limit": limit, "search": search_query}
    if start_date and end_date:
        kwargs["start_date"] = start_date
        kwargs["end_date"] = end_date
    elif start_date or end_date:
        click.echo("Error: both --start-date and --end-date are required together.", err=True)
        raise SystemExit(2)

    if category:
        kwargs["category_ids"] = [category]
    if account:
        kwargs["account_ids"] = [account]

    result = asyncio.run(mm.get_transactions(**kwargs))
    txns = result.get("allTransactions", {}).get("results", [])
    total = result.get("allTransactions", {}).get("totalCount", 0)

    rows = _format_transactions(txns)
    if fmt == "table":
        click.echo(f"Found {total} transactions (showing {len(rows)})\n")
    render(rows, fmt, headers=HEADERS)
