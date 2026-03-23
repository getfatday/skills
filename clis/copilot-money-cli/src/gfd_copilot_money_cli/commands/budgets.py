"""Budgets command — show budget vs actual spending."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, error, render


@click.command()
@click.option("--month", default=None, help="Filter by month (YYYY-MM).")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def budgets(month: str | None, fmt: str | None) -> None:
    """Show budgets with spending progress."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_budgets, get_categories, get_transactions

        budget_list = get_budgets()
        cats = get_categories()
        cat_map = {c.category_id: c.name for c in cats}

        # Filter budgets by month if specified
        if month is not None:
            budget_list = [
                b for b in budget_list
                if b.start_date.startswith(month) or b.period.startswith(month)
            ]

        # Calculate spent per category for the budget periods
        txns = get_transactions()
        if month is not None:
            txns = [t for t in txns if t.date.startswith(month)]

        # Sum spending by category (positive amounts = expenses in Copilot Money)
        spent_by_cat: dict[str, float] = {}
        for t in txns:
            if t.amount > 0 and not t.internal_transfer:
                spent_by_cat[t.category_id] = spent_by_cat.get(t.category_id, 0.0) + t.amount

    except FileNotFoundError as e:
        error(str(e))

    rows = []
    for b in sorted(budget_list, key=lambda b: cat_map.get(b.category_id, "").lower()):
        cat_name = cat_map.get(b.category_id, b.category_id)
        spent = spent_by_cat.get(b.category_id, 0.0)
        remaining = b.amount - spent
        rows.append({
            "category": cat_name,
            "budgeted": f"${abs(b.amount):,.2f}",
            "spent": f"${abs(spent):,.2f}",
            "remaining": f"${abs(remaining):,.2f}"
            if remaining >= 0
            else f"-${abs(remaining):,.2f}",
        })

    render(rows, fmt, headers=["category", "budgeted", "spent", "remaining"])
