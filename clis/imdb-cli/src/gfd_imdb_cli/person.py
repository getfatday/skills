"""Person commands: info, filmography, full."""

from __future__ import annotations

import asyncio

import click

from gfd_imdb_cli.client import get_person, get_person_credits, get_person_full
from gfd_imdb_cli.output import (
    detect_format,
    error,
    name_link,
    render,
    render_single,
    title_link,
)


def _normalize_person_id(pid: str) -> str:
    """Ensure person ID has 'nm' prefix."""
    if pid.startswith("nm"):
        return pid
    return f"nm{pid.lstrip('0') or '0'}"


def _parse_person_info(p: dict, pid: str, *, use_links: bool = False) -> dict:
    """Extract person info fields from GraphQL response."""
    birth_date = ""
    bd = p.get("birthDate")
    if bd:
        dc = bd.get("dateComponents") or {}
        year = str(dc.get("year", ""))
        month = str(dc.get("month", "")).zfill(2)
        day = str(dc.get("day", "")).zfill(2)
        parts = [year, month, day]
        birth_date = "-".join(part for part in parts if part and part != "00")

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

    person_name = (p.get("nameText") or {}).get("text", "")
    person_id = p.get("id", pid)
    if use_links:
        person_name = name_link(person_id, person_name)

    return {
        "id": person_id,
        "name": person_name,
        "birth_date": birth_date,
        "birth_place": (p.get("birthLocation") or {}).get("text", ""),
        "bio": bio,
        "filmography": film_summary,
    }


def _parse_credits(credits: list[dict], *, use_links: bool = False) -> list[dict]:
    """Extract filmography rows from credit nodes."""
    rows = []
    for node in credits:
        title = node.get("title") or {}
        category = node.get("category") or {}
        title_text = (title.get("titleText") or {}).get("text", "")
        title_id = title.get("id", "")
        if use_links and title_id:
            title_text = title_link(title_id, title_text)
        rows.append({
            "role": category.get("text", ""),
            "title": title_text,
            "year": (title.get("releaseYear") or {}).get("year", ""),
            "id": title_id,
        })
    return rows


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

    use_links = fmt == "table"
    data = _parse_person_info(p, pid, use_links=use_links)
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

    use_links = fmt == "table"
    rows = _parse_credits(credits, use_links=use_links)
    render(rows, fmt, headers=["role", "title", "year", "id"])


@person.command("full")
@click.argument("person_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def person_full(person_id: str, fmt: str | None) -> None:
    """Person bio and filmography combined."""
    fmt = detect_format(fmt)
    pid = _normalize_person_id(person_id)
    try:
        p, credits = asyncio.run(get_person_full(pid))
    except Exception as e:
        error(f"IMDB request failed: {e}")

    if not p:
        error(f"Person not found: {person_id}")

    use_links = fmt == "table"
    info_data = _parse_person_info(p, pid, use_links=use_links)
    credit_rows = _parse_credits(credits, use_links=use_links)

    if fmt == "json":
        import json
        click.echo(json.dumps({"info": info_data, "filmography": credit_rows}, indent=2, default=str))
    elif fmt == "csv":
        # CSV: output info as key-value rows, then blank line, then filmography table
        for k, v in info_data.items():
            click.echo(f"{k},{v}")
        click.echo()
        render(credit_rows, "csv", headers=["role", "title", "year", "id"])
    else:
        # Table: bio section then filmography table
        render_single(info_data, "table")
        click.echo()
        if credit_rows:
            render(credit_rows, "table", headers=["role", "title", "year", "id"])
        else:
            click.echo("No filmography found.")
