"""Movie commands: info, cast, box-office."""

from __future__ import annotations

import click
from imdb import IMDbError

from gfd_imdb_cli.client import get_client
from gfd_imdb_cli.context import normalize_id
from gfd_imdb_cli.output import detect_format, error, render, render_single


@click.group("movie")
def movie() -> None:
    """Get movie details."""


@movie.command("info")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_info(movie_id: str, fmt: str | None) -> None:
    """Full movie details by IMDB ID."""
    fmt = detect_format(fmt)
    ia = get_client()
    mid = normalize_id(movie_id)
    try:
        m = ia.get_movie(mid)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    if not m or not m.data:
        error(f"Movie not found: {movie_id}")

    director_list = m.get("directors") or m.get("director") or []
    directors = ", ".join(p.get("name", "") for p in director_list)
    writers = ", ".join(p.get("name", "") for p in (m.get("writers") or m.get("writer") or []))
    cast_list = m.get("cast") or []
    cast_names = ", ".join(p.get("name", "") for p in cast_list[:10])
    genres = ", ".join(m.get("genres") or [])
    runtimes = m.get("runtimes") or []
    runtime = runtimes[0] if runtimes else ""

    data = {
        "id": f"tt{m.movieID}",
        "title": m.get("title", ""),
        "year": m.get("year", ""),
        "rating": m.get("rating", ""),
        "votes": m.get("votes", ""),
        "runtime": f"{runtime} min" if runtime else "",
        "genres": genres,
        "directors": directors,
        "writers": writers,
        "cast": cast_names,
        "plot": (m.get("plot") or [""])[0] if m.get("plot") else "",
    }

    render_single(data, fmt)


@movie.command("cast")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_cast(movie_id: str, fmt: str | None) -> None:
    """Full cast list with roles."""
    fmt = detect_format(fmt)
    ia = get_client()
    mid = normalize_id(movie_id)
    try:
        m = ia.get_movie(mid)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    if not m or not m.data:
        error(f"Movie not found: {movie_id}")

    cast_list = m.get("cast") or []
    rows = []
    for p in cast_list:
        role = p.currentRole
        if hasattr(role, "get"):
            role_name = role.get("name", "")
        elif hasattr(role, "__iter__") and not isinstance(role, str):
            role_name = ", ".join(r.get("name", "") for r in role if hasattr(r, "get"))
        else:
            role_name = str(role) if role else ""
        rows.append({
            "id": f"nm{p.personID}",
            "name": p.get("name", ""),
            "role": role_name,
        })

    render(rows, fmt, headers=["id", "name", "role"])


@movie.command("box-office")
@click.argument("movie_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def movie_box_office(movie_id: str, fmt: str | None) -> None:
    """Box office data for a movie."""
    fmt = detect_format(fmt)
    ia = get_client()
    mid = normalize_id(movie_id)
    try:
        m = ia.get_movie(mid)
        ia.update(m, info=["box office"])
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    if not m or not m.data:
        error(f"Movie not found: {movie_id}")

    box = m.get("box office") or {}
    if not box:
        error(f"No box office data for {movie_id}")

    data = {
        "id": f"tt{m.movieID}",
        "title": m.get("title", ""),
        "budget": box.get("Budget", "N/A"),
        "opening_weekend": box.get("Opening Weekend United States", "N/A"),
        "gross_domestic": box.get("Gross United States and Canada", "N/A"),
        "gross_worldwide": box.get("Cumulative Worldwide Gross", "N/A"),
    }

    render_single(data, fmt)
