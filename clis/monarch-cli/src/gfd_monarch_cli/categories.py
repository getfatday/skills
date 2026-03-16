"""Category commands: list, create."""

from __future__ import annotations

import asyncio

import click

from gfd_monarch_cli.auth import get_client
from gfd_monarch_cli.output import detect_format, render


@click.group("categories")
def categories() -> None:
    """View and manage transaction categories."""


@categories.command("list")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
@click.option("--include-disabled", is_flag=True, help="Include disabled categories")
def list_categories(fmt: str | None, include_disabled: bool) -> None:
    """List all transaction categories."""
    fmt = detect_format(fmt)
    mm = get_client()
    result = asyncio.run(mm.get_transaction_categories())
    cats = result.get("categories", [])

    if not include_disabled:
        cats = [c for c in cats if not c.get("isDisabled")]

    rows = []
    for c in cats:
        rows.append({
            "id": c["id"],
            "name": c.get("name", ""),
            "group": (c.get("group") or {}).get("name", ""),
            "type": (c.get("group") or {}).get("type", ""),
            "system": c.get("isSystemCategory", False),
        })

    render(rows, fmt, headers=["id", "name", "group", "type", "system"])


@categories.command("create")
@click.argument("name")
@click.option("--group-id", required=True, help="Category group ID to add this category to")
def create_category(name: str, group_id: str) -> None:
    """Create a custom category."""
    mm = get_client()
    result = asyncio.run(mm.create_transaction_category(
        group_id=group_id,
        transaction_category_name=name,
    ))
    click.echo(f"Created category: {name}")
    if result:
        cat = result.get("createCategory", {}).get("category", {})
        if cat.get("id"):
            click.echo(f"  ID: {cat['id']}")
