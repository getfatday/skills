"""Person commands: info, filmography."""

from __future__ import annotations

import click
from imdb import IMDbError

from gfd_imdb_cli.client import get_client
from gfd_imdb_cli.output import detect_format, error, render, render_single


def _normalize_person_id(pid: str) -> str:
    """Strip optional 'nm' prefix from person IDs."""
    if pid.startswith("nm"):
        pid = pid[2:]
    return pid.lstrip("0") or "0"


@click.group("person")
def person() -> None:
    """Get person details."""


@person.command("info")
@click.argument("person_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def person_info(person_id: str, fmt: str | None) -> None:
    """Person details by IMDB ID."""
    fmt = detect_format(fmt)
    ia = get_client()
    pid = _normalize_person_id(person_id)
    try:
        p = ia.get_person(pid)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    if not p or not p.data:
        error(f"Person not found: {person_id}")

    filmography = p.get("filmography") or {}
    film_summary_parts = []
    for role, movies in filmography.items():
        film_summary_parts.append(f"{role}: {len(movies)}")
    film_summary = ", ".join(film_summary_parts[:5])

    bio_list = p.get("mini biography") or p.get("biography") or []
    bio = bio_list[0] if bio_list else ""
    if len(bio) > 300:
        bio = bio[:297] + "..."

    data = {
        "id": f"nm{p.personID}",
        "name": p.get("name", ""),
        "birth_date": p.get("birth date", ""),
        "birth_place": p.get("birth notes", ""),
        "bio": bio,
        "filmography": film_summary,
    }

    render_single(data, fmt)


@person.command("filmography")
@click.argument("person_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def person_filmography(person_id: str, fmt: str | None) -> None:
    """Full filmography for a person."""
    fmt = detect_format(fmt)
    ia = get_client()
    pid = _normalize_person_id(person_id)
    try:
        p = ia.get_person(pid)
    except IMDbError as e:
        error(f"IMDB request failed: {e}")

    if not p or not p.data:
        error(f"Person not found: {person_id}")

    filmography = p.get("filmography") or {}
    rows = []
    for role, movies in filmography.items():
        for m in movies:
            rows.append({
                "role": role,
                "title": m.get("title", ""),
                "year": m.get("year", ""),
                "id": f"tt{m.movieID}" if hasattr(m, "movieID") else "",
            })

    render(rows, fmt, headers=["role", "title", "year", "id"])
