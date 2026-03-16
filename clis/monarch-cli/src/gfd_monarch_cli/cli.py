"""Main CLI entry point for gfd-monarch."""

from __future__ import annotations

import click

from gfd_monarch_cli import __version__


@click.group()
@click.version_option(version=__version__, prog_name="gfd-monarch")
def cli() -> None:
    """Personal finance CLI wrapping Monarch Money."""


# Register subcommands
from gfd_monarch_cli.auth import auth
from gfd_monarch_cli.accounts import accounts
from gfd_monarch_cli.transactions import transactions
from gfd_monarch_cli.categories import categories
from gfd_monarch_cli.budgets import budgets
from gfd_monarch_cli.cashflow import cashflow
from gfd_monarch_cli.recurring import recurring

cli.add_command(auth)
cli.add_command(accounts)
cli.add_command(transactions)
cli.add_command(categories)
cli.add_command(budgets)
cli.add_command(cashflow)
cli.add_command(recurring)
