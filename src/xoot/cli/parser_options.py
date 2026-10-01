"""
Option groups the xoot subcommands share: the global --db and --json, the
--project selection and the --yes confirmation.
"""

import argparse

PROJECT_HELP = (
    "project alias or key prefix (default: the project whose path contains "
    "the working directory)"
)


def global_options(default: object) -> argparse.ArgumentParser:
    """
    Build the --db and --json options as a parent parser.

    Args:
        - default (object): None on the top-level parser, SUPPRESS on each
          subparser, so a value after the command overrides the top level.

    Returns:
        - options (argparse.ArgumentParser): a parent parser without help.
    """
    options = argparse.ArgumentParser(add_help=False)
    group = options.add_argument_group("global options")
    group.add_argument(
        "--db",
        metavar="PATH",
        default=default,
        help="database file (default: $XDG_DATA_HOME/xoot/xoot.db)",
    )
    group.add_argument(
        "--json",
        action="store_true",
        default=False if default is None else default,
        help="print results as JSON",
    )
    return options


def select(command: argparse.ArgumentParser, help_text: str = PROJECT_HELP) -> None:
    """
    Add --project to a command.

    Args:
        - command (argparse.ArgumentParser): the subcommand.
        - help_text (str): the option's help.
    """
    group = command.add_argument_group("project selection")
    group.add_argument("--project", metavar="NAME", help=help_text)


def confirm(command: argparse.ArgumentParser) -> None:
    """
    Add --yes to a command that asks before it writes.

    Args:
        - command (argparse.ArgumentParser): the subcommand.
    """
    group = command.add_argument_group("confirmation")
    group.add_argument(
        "--yes", action="store_true", help="apply without asking (needed without a TTY)"
    )
