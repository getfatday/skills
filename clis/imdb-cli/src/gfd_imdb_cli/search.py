"""Search commands: movies, people."""

from __future__ import annotations

import click
from imdb import IMDbError

from gfd_imdb_cli.client import get_client
from gfd_imdb_cli.output import detect_format, error, render


@click.group("search")
def search() -> None:
    """Search IMDB for movies or people."""


@search.command("movies")
@click.argument("query")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def search_movies(query: str, fmt: str | None) -> None:
    """Search movies by title."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.search_movie(query)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for m in results:
        rows.append({
            "id": f"tt{m.movieID}",
            "title": m.get("title", ""),
            "year": m.get("year", ""),
            "rating": m.get("rating", ""),
        })

    render(rows, fmt, headers=["id", "title", "year", "rating"])


@search.command("people")
@click.argument("query")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def search_people(query: str, fmt: str | None) -> None:
    """Search people by name."""
    fmt = detect_format(fmt)
    ia = get_client()
    try:
        results = ia.search_person(query)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for p in results:
        known_for = ", ".join(
            m.get("title", "") for m in (p.get("known for") or [])[:3]
        )
        rows.append({
            "id": f"nm{p.personID}",
            "name": p.get("name", ""),
            "known_for": known_for,
        })

    render(rows, fmt, headers=["id", "name", "known_for"])
