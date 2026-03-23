"""Interactive REPL mode for Copilot Money CLI."""

from __future__ import annotations

import shlex

import click

from gfd_copilot_money_cli.utils.repl_skin import ReplSkin


def start_repl(cli_group: click.Group) -> None:
    """Start interactive REPL session."""
    skin = ReplSkin("copilot-money", version="0.1.0")
    skin.print_banner()

    try:
        pt_session = skin.create_prompt_session()
    except Exception:
        pt_session = None

    while True:
        try:
            if pt_session:
                line = skin.get_input(pt_session).strip()
            else:
                line = input("copilot-money> ").strip()
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            skin.print_goodbye()
            break
        if line.lower() in ("help", "?"):
            cmds = {
                name: cmd.get_short_help_str()
                for name, cmd in cli_group.commands.items()
            }
            skin.help(cmds)
            continue

        try:
            args = shlex.split(line)
        except ValueError as e:
            skin.error(f"Invalid input: {e}")
            continue

        try:
            cli_group(args, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))
