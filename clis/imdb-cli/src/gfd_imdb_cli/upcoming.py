"""Upcoming releases command."""

from __future__ import annotations

import click

from gfd_imdb_cli.client import get_upcoming
from gfd_imdb_cli.output import detect_format, error, render


@click.command("upcoming")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def upcoming(fmt: str | None) -> None:
    """Upcoming movie releases."""
    fmt = detect_format(fmt)
    try:
        results = get_upcoming()
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for entry in results:
        rows.append({
            "id": entry.get("id", ""),
            "title": entry.get("titleText", ""),
            "year": "",
        })

    render(rows, fmt, headers=["id", "title", "year"])
