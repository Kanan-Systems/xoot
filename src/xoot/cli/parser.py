"""
The xoot argument parser.

--db and --json are accepted before or after the command: each subparser
repeats them with SUPPRESS defaults, so a value given after the command
overrides the top-level default and an absent one leaves it alone.
"""

import argparse

from xoot import __version__
from xoot.cli.commands import (
    brief,
    dashboard,
    db,
    init,
    paste,
    redact,
    workflow,
)
from xoot.cli.parser_options import confirm, global_options, select
from xoot.cli.parser_project import add_backlog, add_project
from xoot.dashboard.ports import DEFAULT_PORT
from xoot.models.event.redactable_field import RedactableField
from xoot.models.item.tree_query import MAX_DEPTH


def build_parser() -> argparse.ArgumentParser:
    """
    Build the parser for every command.

    Returns:
        - parser (argparse.ArgumentParser): parses into a namespace whose
          handler field is the command to run.
    """
    common = global_options(argparse.SUPPRESS)
    parser = argparse.ArgumentParser(
        prog="xoot",
        description="Local tracker for goals, batches and subtasks.",
        parents=[global_options(None)],
    )
    parser.add_argument("--version", action="version", version=f"xoot {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    _init(commands, common)
    add_project(commands, common)
    _views(commands, common)
    add_backlog(commands, common)
    _workflow(commands, common)
    _redact(commands, common)
    _paste(commands, common)
    _db(commands, common)
    _dashboard(commands, common)
    return parser


def _dashboard(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    command = commands.add_parser(
        "dashboard",
        parents=[common],
        help="serve the web dashboard (view and edit) on 127.0.0.1",
    )
    group = command.add_argument_group("dashboard")
    group.add_argument(
        "--port",
        type=_port,
        default=DEFAULT_PORT,
        metavar="N",
        help=f"TCP port on 127.0.0.1 (default: {DEFAULT_PORT})",
    )
    group.add_argument(
        "--open", action="store_true", help="also open the URL in a browser"
    )
    command.set_defaults(handler=dashboard.run_dashboard)


def _port(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError("must be a port number, 1-65535")
    return value


def _init(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    command = commands.add_parser(
        "init", parents=[common], help="register a project for a directory"
    )
    command.add_argument(
        "path", nargs="?", metavar="PATH", help="directory (default: the working one)"
    )
    group = command.add_argument_group("project")
    group.add_argument(
        "--prefix",
        required=True,
        help="key prefix, e.g. xoot: 2-32 lowercase letters or digits, starting "
        "with a letter; no dashes",
    )
    group.add_argument("--name", help="display name (default: the prefix)")
    group.add_argument(
        "--alias",
        action="append",
        default=[],
        help="an alias; may be repeated; may contain dashes but must not look "
        "like a key segment (goal-12, backlog-3)",
    )
    command.set_defaults(handler=init.run_init)


def _views(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    brief_command = commands.add_parser(
        "brief", parents=[common], help="summarize a project"
    )
    select(brief_command)
    brief_command.set_defaults(handler=brief.run_brief)
    tree = commands.add_parser("tree", parents=[common], help="show the item tree")
    select(tree)
    group = tree.add_argument_group("tree")
    group.add_argument(
        "--root", metavar="KEY", help="item key to start from (or <prefix>:<key>)"
    )
    group.add_argument(
        "--depth",
        type=_depth,
        default=3,
        metavar="N",
        help=f"levels below the roots, 0-{MAX_DEPTH} (default: 3)",
    )
    group.add_argument(
        "--all", action="store_true", help="include done and dropped items"
    )
    tree.set_defaults(handler=brief.run_tree)


def _workflow(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    group = commands.add_parser("workflow", help="export or import a workflow file")
    actions = group.add_subparsers(dest="action", required=True, metavar="ACTION")
    export = actions.add_parser(
        "export", parents=[common], help="print or write the active workflow as TOML"
    )
    select(export)
    export.add_argument("-o", "--output", metavar="FILE", help="write to FILE")
    export.set_defaults(handler=workflow.run_export)
    imported = actions.add_parser(
        "import", parents=[common], help="replace the workflow with a TOML file"
    )
    imported.add_argument(
        "file", metavar="FILE", help="a TOML workflow, at most 64 KiB"
    )
    select(imported)
    mapping = imported.add_argument_group("state mapping")
    mapping.add_argument(
        "--map",
        action="append",
        default=[],
        type=workflow.parse_move,
        metavar="KIND:OLD=NEW",
        help="move items of KIND in removed state OLD to NEW; may be repeated",
    )
    confirm(imported)
    imported.set_defaults(handler=workflow.run_import)


def _redact(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    command = commands.add_parser(
        "redact", parents=[common], help="clear a text field and its history"
    )
    command.add_argument(
        "key",
        metavar="KEY",
        help="an item or decision key (optionally <prefix>:<key>), or a key "
        "prefix alone for the project name",
    )
    command.add_argument(
        "field", metavar="FIELD", choices=[f.value for f in RedactableField]
    )
    select(command)
    confirm(command)
    command.set_defaults(handler=redact.run_redact)


def _paste(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    group = commands.add_parser(
        "paste", help="apply an xoot block from a chat reply, or print its brief"
    )
    actions = group.add_subparsers(dest="action", required=True, metavar="ACTION")
    brief_command = actions.add_parser(
        "brief", parents=[common], help="print the markdown brief to paste into a chat"
    )
    select(brief_command)
    brief_command.set_defaults(handler=paste.run_brief)
    applied = actions.add_parser(
        "apply", parents=[common], help="preview, confirm and apply one xoot block"
    )
    applied.add_argument(
        "source",
        metavar="SOURCE",
        help='a file or pipe holding the reply, or "-" for stdin; at most 256 KiB',
    )
    group_confirm = applied.add_argument_group("confirmation")
    group_confirm.add_argument(
        "--yes",
        action="store_true",
        help="apply without asking on the terminal; the plan is still printed",
    )
    applied.set_defaults(handler=paste.run_apply)


def _db(commands: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    group = commands.add_parser("db", help="database statistics and maintenance")
    actions = group.add_subparsers(dest="action", required=True, metavar="ACTION")
    stats = actions.add_parser(
        "stats", parents=[common], help="page, size and row counts"
    )
    stats.set_defaults(handler=db.run_stats)
    vacuum = actions.add_parser(
        "vacuum", parents=[common], help="rebuild the file without free pages"
    )
    vacuum.set_defaults(handler=db.run_vacuum)


def _depth(text: str) -> int:
    try:
        depth = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if not 0 <= depth <= MAX_DEPTH:
        raise argparse.ArgumentTypeError(f"expected 0 to {MAX_DEPTH}")
    return depth
