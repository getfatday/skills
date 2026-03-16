"""Shared output formatting: json, table, csv."""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import Any

import click
from tabulate import tabulate


_IMDB_TITLE_URL = "https://www.imdb.com/title/{id}/"
_IMDB_NAME_URL = "https://www.imdb.com/name/{id}/"


def is_tty() -> bool:
    return sys.stdout.isatty()


def detect_format(explicit: str | None) -> str:
    if explicit:
        return explicit
    return "table" if is_tty() else "json"


def hyperlink(url: str, text: str) -> str:
    """Wrap text in an OSC 8 terminal hyperlink if stdout is a TTY.

    Returns plain text when output is piped or redirected.
    """
    if not is_tty():
        return text
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def title_link(title_id: str, text: str) -> str:
    """Make text a clickable link to an IMDB title page (TTY only)."""
    url = _IMDB_TITLE_URL.format(id=title_id)
    return hyperlink(url, text)


def name_link(name_id: str, text: str) -> str:
    """Make text a clickable link to an IMDB person page (TTY only)."""
    url = _IMDB_NAME_URL.format(id=name_id)
    return hyperlink(url, text)


def render(data: list[dict[str, Any]], fmt: str, headers: list[str] | None = None) -> None:
    if not data:
        if fmt == "json":
            click.echo("[]")
        else:
            click.echo("No results.")
        return

    if fmt == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    elif fmt == "csv":
        keys = headers or list(data[0].keys())
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
        click.echo(buf.getvalue().rstrip())
    else:
        keys = headers or list(data[0].keys())
        rows = [[row.get(k, "") for k in keys] for row in data]
        click.echo(tabulate(rows, headers=keys, tablefmt="simple"))


def render_single(data: dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        max_key = max(len(k) for k in data) if data else 0
        for k, v in data.items():
            click.echo(f"{k:<{max_key}}  {v}")


def error(message: str, code: int = 1) -> None:
    click.echo(f"Error: {message}", err=True)
    raise SystemExit(code)
