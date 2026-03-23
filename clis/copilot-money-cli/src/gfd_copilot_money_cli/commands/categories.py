"""Categories command — list spending categories."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, error, render


@click.command()
@click.option("--flat", is_flag=True, default=False, help="Flat list instead of tree view.")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def categories(flat: bool, fmt: str | None) -> None:
    """List spending categories (tree view by default)."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_categories

        cats = get_categories()
    except FileNotFoundError as e:
        error(str(e))

    cats.sort(key=lambda c: (c.group.lower(), c.order, c.name.lower()))

    if flat or fmt in ("json", "csv"):
        rows = [
            {
                "name": c.name,
                "emoji": c.icon,
                "parent": c.group,
            }
            for c in cats
        ]
        render(rows, fmt, headers=["name", "emoji", "parent"])
    else:
        # Tree view grouped by category group
        current_group = ""
        for c in cats:
            if c.group and c.group != current_group:
                current_group = c.group
                click.echo(f"\n{current_group}")
            prefix = c.icon + " " if c.icon else "  "
            click.echo(f"  {prefix}{c.name}")
