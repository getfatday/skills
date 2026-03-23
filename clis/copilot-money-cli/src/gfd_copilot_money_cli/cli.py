"""Copilot Money personal finance CLI — reads local cache, no API needed."""

from __future__ import annotations

import click

from gfd_copilot_money_cli import __version__
from gfd_copilot_money_cli.commands.status import status
from gfd_copilot_money_cli.commands.accounts import accounts
from gfd_copilot_money_cli.commands.transactions import transactions
from gfd_copilot_money_cli.commands.categories import categories
from gfd_copilot_money_cli.commands.budgets import budgets
from gfd_copilot_money_cli.commands.recurring import recurring
from gfd_copilot_money_cli.commands.summary import summary


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="gfd-copilot-money")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Copilot Money personal finance CLI — reads local cache, no API needed."""
    if ctx.invoked_subcommand is None:
        from gfd_copilot_money_cli.repl import start_repl

        start_repl(cli)


cli.add_command(status)
cli.add_command(accounts)
cli.add_command(transactions)
cli.add_command(categories)
cli.add_command(budgets)
cli.add_command(recurring)
cli.add_command(summary)

if __name__ == "__main__":
    cli()
