"""Summary command — financial overview for a period."""

from __future__ import annotations

from collections import defaultdict

import click

from gfd_copilot_money_cli.output import detect_format, render_single, render, error


@click.command()
@click.option("--period", default=None, help="Month to summarize (YYYY-MM).")
@click.option("--start", "start_date", default=None, help="Start date (YYYY-MM-DD).")
@click.option("--end", "end_date", default=None, help="End date (YYYY-MM-DD).")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def summary(
    period: str | None,
    start_date: str | None,
    end_date: str | None,
    fmt: str | None,
) -> None:
    """Show financial summary: net worth, income, expenses, top categories."""
    fmt = detect_format(fmt)

    # Determine date range from --period or --start/--end
    if period is not None:
        start_date = f"{period}-01"
        # Approximate end of month
        year, month_str = period.split("-")
        m = int(month_str)
        if m == 12:
            end_date = f"{int(year) + 1}-01-01"
        else:
            end_date = f"{year}-{m + 1:02d}-01"

    try:
        from gfd_copilot_money_cli.core.store import get_transactions, get_accounts, get_categories

        txns = get_transactions(start_date=start_date, end_date=end_date)
        accts = get_accounts()
        cats = get_categories()
        cat_map = {c.category_id: c.name for c in cats}
    except FileNotFoundError as e:
        error(str(e))

    # Net worth = sum of all account balances
    net_worth = sum(a.current_balance for a in accts)

    # Income (negative amounts) and expenses (positive amounts) in Copilot Money
    total_income = 0.0
    total_expenses = 0.0
    spending_by_cat: dict[str, float] = defaultdict(float)

    for t in txns:
        if t.internal_transfer:
            continue
        if t.amount < 0:
            total_income += abs(t.amount)
        elif t.amount > 0:
            total_expenses += t.amount
            cat_name = cat_map.get(t.category_id, "Uncategorized")
            spending_by_cat[cat_name] += t.amount

    net = total_income - total_expenses

    data: dict[str, object] = {
        "net_worth": f"${net_worth:,.2f}",
        "total_income": f"${total_income:,.2f}",
        "total_expenses": f"${total_expenses:,.2f}",
        "net": f"${net:,.2f}" if net >= 0 else f"-${abs(net):,.2f}",
        "transactions": len(txns),
    }

    if fmt == "json":
        import json
        # Include top categories in JSON output
        top_cats = sorted(spending_by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
        json_data = {
            **data,
            "top_categories": [{"category": name, "amount": f"${amt:,.2f}"} for name, amt in top_cats],
        }
        click.echo(json.dumps(json_data, indent=2, default=str))
    else:
        render_single(data, fmt)

        # Show top spending categories
        top_cats = sorted(spending_by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
        if top_cats:
            click.echo("\nTop spending categories:")
            cat_rows = [
                {"category": name, "amount": f"${amt:,.2f}"}
                for name, amt in top_cats
            ]
            render(cat_rows, "table", headers=["category", "amount"])
