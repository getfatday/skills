"""Person commands: info, filmography."""

from __future__ import annotations

import click

from gfd_imdb_cli.client import get_person, get_person_credits
from gfd_imdb_cli.output import detect_format, error, render, render_single


def _normalize_person_id(pid: str) -> str:
    """Ensure person ID has 'nm' prefix."""
    if pid.startswith("nm"):
        return pid
    return f"nm{pid.lstrip('0') or '0'}"


@click.group("person")
def person() -> None:
    """Get person details."""


@person.command("info")
@click.argument("person_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def person_info(person_id: str, fmt: str | None) -> None:
    """Person details by IMDB ID."""
    fmt = detect_format(fmt)
    pid = _normalize_person_id(person_id)
    try:
        p = get_person(pid)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    if not p:
        error(f"Person not found: {person_id}")

    birth_date = ""
    bd = p.get("birthDate")
    if bd:
        dc = bd.get("dateComponents") or {}
        year = str(dc.get("year", ""))
        month = str(dc.get("month", "")).zfill(2)
        day = str(dc.get("day", "")).zfill(2)
        parts = [year, month, day]
        birth_date = "-".join(p for p in parts if p and p != "00")

    bio = ""
    bio_obj = p.get("bio")
    if bio_obj:
        text_obj = bio_obj.get("text")
        if text_obj:
            bio = text_obj.get("plainText", "")
    if len(bio) > 300:
        bio = bio[:297] + "..."

    known_for = p.get("knownFor") or {}
    kf_edges = known_for.get("edges") or []
    film_summary = ", ".join(
        "{} ({})".format(
            e["node"]["title"]["titleText"]["text"],
            e["node"]["title"]["releaseYear"]["year"],
        )
        for e in kf_edges
        if e.get("node", {}).get("title")
    )

    data = {
        "id": p.get("id", pid),
        "name": (p.get("nameText") or {}).get("text", ""),
        "birth_date": birth_date,
        "birth_place": (p.get("birthLocation") or {}).get("text", ""),
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
    pid = _normalize_person_id(person_id)
    try:
        credits = get_person_credits(pid)
    except Exception as e:
        error(f"IMDB request failed: {e}")

    rows = []
    for node in credits:
        title = node.get("title") or {}
        category = node.get("category") or {}
        rows.append({
            "role": category.get("text", ""),
            "title": (title.get("titleText") or {}).get("text", ""),
            "year": (title.get("releaseYear") or {}).get("year", ""),
            "id": title.get("id", ""),
        })

    render(rows, fmt, headers=["role", "title", "year", "id"])
