"""Main CLI entry point for gfd-imdb."""

from __future__ import annotations

import click

from gfd_imdb_cli import __version__
from gfd_imdb_cli.movie import movie
from gfd_imdb_cli.person import person
from gfd_imdb_cli.search import search
from gfd_imdb_cli.top import top
from gfd_imdb_cli.upcoming import upcoming


@click.group()
@click.version_option(version=__version__, prog_name="gfd-imdb")
def cli() -> None:
    """IMDB data CLI using Cinemagoer."""


cli.add_command(search)
cli.add_command(movie)
cli.add_command(person)
cli.add_command(top)
cli.add_command(upcoming)
