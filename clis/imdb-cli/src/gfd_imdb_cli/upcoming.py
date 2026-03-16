"""Upcoming releases command."""

from __future__ import annotations

import click
from imdb import IMDbError

from gfd_imdb_cli.client import get_client
from gfd_imdb_cli.output import detect_format, error, render


@click.command("upcoming")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def upcoming(fmt: str | None) -> None:
    """Upcoming movie releases."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.get_coming_soon_movies()
    except (IMDbError, AttributeError) as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for m in results:
        rows.append({
            "id": f"tt{m.movieID}",
            "title": m.get("title", ""),
            "year": m.get("year", ""),
        })

    render(rows, fmt, headers=["id", "title", "year"])
