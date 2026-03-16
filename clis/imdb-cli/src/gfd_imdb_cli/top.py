"""Top lists commands: movies, shows, box-office."""

from __future__ import annotations

import click

from gfd_imdb_cli.client import get_box_office_chart, get_top_movies, get_top_tv
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
    try:
        results = get_top_movies(limit)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for edge in results:
        node = edge["node"]
        ratings = node.get("ratingsSummary") or {}
        rows.append({
            "rank": edge.get("currentRank", ""),
            "id": node.get("id", ""),
            "title": (node.get("titleText") or {}).get("text", ""),
            "year": (node.get("releaseYear") or {}).get("year", ""),
            "rating": ratings.get("aggregateRating", ""),
        })

    render(rows, fmt, headers=["rank", "id", "title", "year", "rating"])


@top.command("shows")
@click.option("--limit", default=25, help="Number of results to show")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def top_shows(limit: int, fmt: str | None) -> None:
    """IMDB Top 250 TV shows."""
    fmt = detect_format(fmt)
    try:
        results = get_top_tv(limit)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for edge in results:
        node = edge["node"]
        ratings = node.get("ratingsSummary") or {}
        rows.append({
            "rank": edge.get("currentRank", ""),
            "id": node.get("id", ""),
            "title": (node.get("titleText") or {}).get("text", ""),
            "year": (node.get("releaseYear") or {}).get("year", ""),
            "rating": ratings.get("aggregateRating", ""),
        })

    render(rows, fmt, headers=["rank", "id", "title", "year", "rating"])


@top.command("box-office")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def top_box_office(fmt: str | None) -> None:
    """Current box office rankings."""
    fmt = detect_format(fmt)
    try:
        results = get_box_office_chart()
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for i, edge in enumerate(results, 1):
        node = edge["node"]
        gross_total = (node.get("gross") or {}).get("total") or {}
        amount = gross_total.get("amount")
        weekend = f"${amount:,.0f}" if amount else ""

        release = node.get("release") or {}
        titles = release.get("titles") or []
        title_info = titles[0] if titles else {}

        rows.append({
            "rank": i,
            "id": title_info.get("id", ""),
            "title": (title_info.get("titleText") or {}).get("text", ""),
            "weekend": weekend,
            "gross": "",
            "weeks": release.get("weeksRunning", ""),
        })

    render(rows, fmt, headers=["rank", "id", "title", "weekend", "gross", "weeks"])
