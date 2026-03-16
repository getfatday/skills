"""Budget commands: list budgets with spending vs planned amounts."""

from __future__ import annotations

import asyncio
from datetime import datetime

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render


@click.group("budgets")
def budgets() -> None:
    """View budget information."""


@budgets.command("list")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
@click.option("--month", default=None, help="Month to show (YYYY-MM), defaults to current")
def list_budgets(fmt: str | None, month: str | None) -> None:
    """Show current budget with planned and actual amounts."""
    fmt = detect_format(fmt)
    mm = get_client()

    if month:
        start_date = f"{month}-01"
        # Parse to get end of month
        dt = datetime.strptime(start_date, "%Y-%m-%d")
        import calendar
        _, last_day = calendar.monthrange(dt.year, dt.month)
        end_date = f"{month}-{last_day:02d}"
    else:
        now = datetime.now()
        start_date = now.strftime("%Y-%m-01")
        import calendar
        _, last_day = calendar.monthrange(now.year, now.month)
        end_date = now.strftime(f"%Y-%m-{last_day:02d}")

    result = asyncio.run(mm.get_budgets(start_date=start_date, end_date=end_date))

    # Build category ID -> name lookup
    cat_groups = result.get("categoryGroups", [])
    cat_map: dict[str, str] = {}
    group_map: dict[str, str] = {}
    for cg in cat_groups:
        group_map[cg["id"]] = cg.get("name", "")
        for cat in cg.get("categories", []):
            cat_map[cat["id"]] = cat.get("name", "")

    budget_data = result.get("budgetData", {})
    by_category = budget_data.get("monthlyAmountsByCategory", [])

    rows = []
    for item in by_category:
        cat_id = item.get("category", {}).get("id", "")
        cat_name = cat_map.get(cat_id, cat_id)
        for ma in item.get("monthlyAmounts", []):
            planned = ma.get("plannedCashFlowAmount", 0) or 0
            actual = ma.get("actualAmount", 0) or 0
            remaining = ma.get("remainingAmount", 0) or 0
            if planned == 0 and actual == 0:
                continue
            rows.append({
                "category": cat_name,
                "planned": f"${planned:,.2f}",
                "actual": f"${actual:,.2f}",
                "remaining": f"${remaining:,.2f}",
                "month": ma.get("month", ""),
            })

    # Add totals from totalsByMonth
    totals = budget_data.get("totalsByMonth", [])
    for t in totals:
        income = t.get("totalIncome", {})
        expenses = t.get("totalExpenses", {})
        rows.append({
            "category": "--- TOTAL INCOME ---",
            "planned": f"${(income.get('plannedAmount', 0) or 0):,.2f}",
            "actual": f"${(income.get('actualAmount', 0) or 0):,.2f}",
            "remaining": f"${(income.get('remainingAmount', 0) or 0):,.2f}",
            "month": t.get("month", ""),
        })
        rows.append({
            "category": "--- TOTAL EXPENSES ---",
            "planned": f"${(expenses.get('plannedAmount', 0) or 0):,.2f}",
            "actual": f"${(expenses.get('actualAmount', 0) or 0):,.2f}",
            "remaining": f"${(expenses.get('remainingAmount', 0) or 0):,.2f}",
            "month": t.get("month", ""),
        })

    render(rows, fmt, headers=["category", "planned", "actual", "remaining", "month"])
