"""Movie commands: info, cast, box-office."""

from __future__ import annotations

import click

from gfd_imdb_cli.client import get_title, get_title_box_office, get_title_cast
from gfd_imdb_cli.context import normalize_id
from gfd_imdb_cli.output import detect_format, error, render, render_single


def _fmt_money(money: dict | None) -> str:
    """Format a money dict like {'amount': 63000000, 'currency': 'USD'}."""
    if not money:
        return "N/A"
    amount = money.get("amount")
    currency = money.get("currency", "")
    if amount is None:
        return "N/A"
    if currency == "USD":
        return f"${amount:,.0f}"
    return f"{currency} {amount:,.0f}"


@click.group("movie")
def movie() -> None:
    """Get movie details."""


@movie.command("info")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_info(movie_id: str, fmt: str | None) -> None:
    """Full movie details by IMDB ID."""
    fmt = detect_format(fmt)
    tid = normalize_id(movie_id)
    try:
        m = get_title(tid)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    if not m:
        error(f"Movie not found: {movie_id}")

    runtime_secs = (m.get("runtime") or {}).get("seconds")
    runtime = f"{runtime_secs // 60} min" if runtime_secs else ""

    genres_list = [g["text"] for g in ((m.get("genres") or {}).get("genres") or [])]
    directors = ", ".join(
        e["node"]["name"]["nameText"]["text"]
        for e in ((m.get("directors") or {}).get("edges") or [])
    )
    writers = ", ".join(
        e["node"]["name"]["nameText"]["text"]
        for e in ((m.get("writers") or {}).get("edges") or [])
    )
    cast_names = ", ".join(
        e["node"]["name"]["nameText"]["text"]
        for e in ((m.get("cast") or {}).get("edges") or [])
    )

    plot = ""
    plot_obj = m.get("plot")
    if plot_obj:
        plot_text = plot_obj.get("plotText")
        if plot_text:
            plot = plot_text.get("plainText", "")

    ratings = m.get("ratingsSummary") or {}

    data = {
        "id": m.get("id", tid),
        "title": (m.get("titleText") or {}).get("text", ""),
        "year": (m.get("releaseYear") or {}).get("year", ""),
        "rating": ratings.get("aggregateRating", ""),
        "votes": ratings.get("voteCount", ""),
        "runtime": runtime,
        "genres": ", ".join(genres_list),
        "directors": directors,
        "writers": writers,
        "cast": cast_names,
        "plot": plot,
    }

    render_single(data, fmt)


@movie.command("cast")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_cast(movie_id: str, fmt: str | None) -> None:
    """Full cast list with roles."""
    fmt = detect_format(fmt)
    tid = normalize_id(movie_id)
    try:
        cast_list = get_title_cast(tid)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for node in cast_list:
        name_obj = node.get("name") or {}
        characters = node.get("characters") or []
        role_name = ", ".join(c.get("name", "") for c in characters)
        rows.append({
            "id": name_obj.get("id", ""),
            "name": (name_obj.get("nameText") or {}).get("text", ""),
            "role": role_name,
        })

    render(rows, fmt, headers=["id", "name", "role"])


@movie.command("box-office")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_box_office(movie_id: str, fmt: str | None) -> None:
    """Box office data for a movie."""
    fmt = detect_format(fmt)
    tid = normalize_id(movie_id)
    try:
        m = get_title_box_office(tid)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    if not m:
        error(f"Movie not found: {movie_id}")

    budget = (m.get("productionBudget") or {}).get("budget")
    opening = ((m.get("openingWeekendGross") or {}).get("gross") or {}).get("total")
    domestic = (m.get("lifetimeGross") or {}).get("total")
    worldwide = (m.get("worldwideGross") or {}).get("total")

    data = {
        "id": m.get("id", tid),
        "title": (m.get("titleText") or {}).get("text", ""),
        "budget": _fmt_money(budget),
        "opening_weekend": _fmt_money(opening),
        "gross_domestic": _fmt_money(domestic),
        "gross_worldwide": _fmt_money(worldwide),
    }

    render_single(data, fmt)
