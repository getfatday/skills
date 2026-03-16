"""Top lists commands: movies, shows, box-office."""

from __future__ import annotations

import click
from imdb import IMDbError

from gfd_imdb_cli.client import get_client
from gfd_imdb_cli.output import detect_format, error, render


@click.group("top")
def top() -> None:
    """IMDB top lists."""


@top.command("movies")
@click.option("--limit", default=25, help="Number of results to show")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def top_movies(limit: int, fmt: str | None) -> None:
    """IMDB Top 250 movies."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.get_top250_movies()
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for i, m in enumerate(results[:limit], 1):
        rows.append({
            "rank": i,
            "id": f"tt{m.movieID}",
            "title": m.get("title", ""),
            "year": m.get("year", ""),
            "rating": m.get("rating", ""),
        })

    render(rows, fmt, headers=["rank", "id", "title", "year", "rating"])


@top.command("shows")
@click.option("--limit", default=25, help="Number of results to show")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def top_shows(limit: int, fmt: str | None) -> None:
    """IMDB Top 250 TV shows."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.get_top250_tv()
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for i, m in enumerate(results[:limit], 1):
        rows.append({
            "rank": i,
            "id": f"tt{m.movieID}",
            "title": m.get("title", ""),
            "year": m.get("year", ""),
            "rating": m.get("rating", ""),
        })

    render(rows, fmt, headers=["rank", "id", "title", "year", "rating"])


@top.command("box-office")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def top_box_office(fmt: str | None) -> None:
    """Current box office rankings."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.get_boxoffice()
    except (IMDbError, AttributeError) as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for i, m in enumerate(results, 1):
        rows.append({
            "rank": i,
            "id": f"tt{m.movieID}",
            "title": m.get("title", ""),
            "weekend": m.get("weekend") or "",
            "gross": m.get("gross") or "",
            "weeks": m.get("weeks") or "",
        })

    render(rows, fmt, headers=["rank", "id", "title", "weekend", "gross", "weeks"])
