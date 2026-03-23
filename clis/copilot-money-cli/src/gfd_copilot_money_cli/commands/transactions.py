"""Transactions command — list and filter transactions."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, render, error


@click.command()
@click.option("--start", "start_date", default=None, help="Start date (YYYY-MM-DD).")
@click.option("--end", "end_date", default=None, help="End date (YYYY-MM-DD).")
@click.option("--category", default=None, help="Filter by category name (substring match).")
@click.option("--account", default=None, help="Filter by account name (substring match).")
@click.option("--min", "min_amount", type=float, default=None, help="Minimum amount.")
@click.option("--max", "max_amount", type=float, default=None, help="Maximum amount.")
@click.option("--exclude-transfers", is_flag=True, default=False, help="Exclude internal transfers.")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def transactions(
    start_date: str | None,
    end_date: str | None,
    category: str | None,
    account: str | None,
    min_amount: float | None,
    max_amount: float | None,
    exclude_transfers: bool,
    fmt: str | None,
) -> None:
    """List transactions with optional filters."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_transactions, get_categories, get_accounts

        # Build lookup maps for name-based filtering
        account_id: str | None = None
        category_ids: set[str] = set()

        if category is not None:
            cats = get_categories()
            cat_lower = category.lower()
            matches = [c for c in cats if cat_lower in c.name.lower()]
            if not matches:
                error(f"No category matching '{category}'")
            category_ids = {c.category_id for c in matches}

        if account is not None:
            accts = get_accounts()
            acct_lower = account.lower()
            matches = [a for a in accts if acct_lower in a.name.lower()]
            if not matches:
                error(f"No account matching '{account}'")
            account_id = matches[0].account_id

        txns = get_transactions(
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
        )

        # Filter by category name (may match multiple category IDs)
        if category is not None:
            txns = [t for t in txns if t.category_id in category_ids]

        # Build lookup maps for display
        all_cats = get_categories()
        cat_map = {c.category_id: c.name for c in all_cats}
        all_accts = get_accounts()
        acct_map = {a.account_id: a.name for a in all_accts}

    except FileNotFoundError as e:
        error(str(e))

    # Apply additional filters
    if min_amount is not None:
        txns = [t for t in txns if t.amount >= min_amount]
    if max_amount is not None:
        txns = [t for t in txns if t.amount <= max_amount]
    if exclude_transfers:
        txns = [t for t in txns if not t.internal_transfer]

    # Sort by date descending
    txns.sort(key=lambda t: t.date, reverse=True)

    rows = [
        {
            "date": t.date,
            "name": t.name,
            "amount": f"${abs(t.amount):,.2f}",
            "category": cat_map.get(t.category_id, ""),
            "account": acct_map.get(t.account_id, ""),
            "pending": "yes" if t.pending else "",
        }
        for t in txns
    ]
    render(rows, fmt, headers=["date", "name", "amount", "category", "account", "pending"])
