"""Search commands: movies, people."""

from __future__ import annotations

import click
import httpx

from gfd_imdb_cli.client import search_suggestions
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
    try:
        results = search_suggestions(query)
    except httpx.HTTPError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for item in results:
        if not item.get("id", "").startswith("tt"):
            continue
        rows.append({
            "id": item["id"],
            "title": item.get("l", ""),
            "year": item.get("y", ""),
            "rating": "",
        })

    render(rows, fmt, headers=["id", "title", "year", "rating"])


@search.command("people")
@click.argument("query")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def search_people(query: str, fmt: str | None) -> None:
    """Search people by name."""
    fmt = detect_format(fmt)
    try:
        results = search_suggestions(query)
    except httpx.HTTPError as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for item in results:
        if not item.get("id", "").startswith("nm"):
            continue
        rows.append({
            "id": item["id"],
            "name": item.get("l", ""),
            "known_for": item.get("s", ""),
        })

    render(rows, fmt, headers=["id", "name", "known_for"])
