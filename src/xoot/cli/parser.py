"""
The xoot argument parser.

--db and --json are accepted before or after the command: each subparser
repeats them with SUPPRESS defaults, so a value given after the command
overrides the top-level default and an absent one leaves it alone.
"""

import argparse

from xoot.cli.commands import brief, db, init, project, redact, workflow
from xoot.models.event.redactable_field import RedactableField
from xoot.models.item.tree_query import MAX_DEPTH

PROJECT_HELP = (
    "project alias or key prefix (default: the project whose path contains "
    "the working directory)"
)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the parser for every command.

    Returns:
        - parser (argparse.ArgumentParser): parses into a namespace whose
          handler field is the command to run.
    """
    common = _global_options(argparse.SUPPRESS)
    parser = argparse.ArgumentParser(
        prog="xoot",
        description="Local tracker for goals, batches and subtasks.",
        parents=[_global_options(None)],
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    _init(commands, common)
    _project(commands, common)
    _views(commands, common)
    _workflow(commands, common)
    _redact(commands, common)
    _db(commands, common)
    return parser


def _global_options(default: object) -> argparse.ArgumentParser:
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
    group.add_argument("--prefix", required=True, help="key prefix, e.g. xoot")
    group.add_argument("--name", help="display name (default: the prefix)")
    group.add_argument(
        "--alias", action="append", default=[], help="an alias; may be repeated"
    )
    command.set_defaults(handler=init.run_init)


def _project(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    group = commands.add_parser(
        "project", help="list and show projects; add or remove aliases and paths"
    )
    actions = group.add_subparsers(dest="action", required=True, metavar="ACTION")
    listing = actions.add_parser("list", parents=[common], help="list every project")
    listing.set_defaults(handler=project.run_list)
    show = actions.add_parser("show", parents=[common], help="show one project")
    _select(show)
    show.set_defaults(handler=project.run_show)
    for name, target, metavar, handler, confirmed in (
        ("add-alias", "alias", "ALIAS", project.run_add_alias, False),
        ("remove-alias", "alias", "ALIAS", project.run_remove_alias, True),
        ("add-path", "path", "PATH", project.run_add_path, False),
        ("remove-path", "path", "PATH", project.run_remove_path, True),
    ):
        verb = "remove" if confirmed else "add"
        action = actions.add_parser(
            name, parents=[common], help=f"{verb} a project {target}"
        )
        action.add_argument(target, metavar=metavar)
        _select(action)
        if confirmed:
            _confirm(action)
        action.set_defaults(handler=handler)


def _views(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    brief_command = commands.add_parser(
        "brief", parents=[common], help="summarize a project"
    )
    _select(brief_command)
    brief_command.set_defaults(handler=brief.run_brief)
    tree = commands.add_parser("tree", parents=[common], help="show the item tree")
    _select(tree)
    group = tree.add_argument_group("tree")
    group.add_argument("--root", metavar="KEY", help="item key to start from")
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
    _select(export)
    export.add_argument("-o", "--output", metavar="FILE", help="write to FILE")
    export.set_defaults(handler=workflow.run_export)
    imported = actions.add_parser(
        "import", parents=[common], help="replace the workflow with a TOML file"
    )
    imported.add_argument(
        "file", metavar="FILE", help="a TOML workflow, at most 64 KiB"
    )
    _select(imported)
    mapping = imported.add_argument_group("state mapping")
    mapping.add_argument(
        "--map",
        action="append",
        default=[],
        type=workflow.parse_move,
        metavar="KIND:OLD=NEW",
        help="move items of KIND in removed state OLD to NEW; may be repeated",
    )
    _confirm(imported)
    imported.set_defaults(handler=workflow.run_import)


def _redact(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    command = commands.add_parser(
        "redact", parents=[common], help="clear a text field and its history"
    )
    command.add_argument(
        "key", metavar="KEY", help="an item, decision or session key, or a prefix"
    )
    command.add_argument(
        "field", metavar="FIELD", choices=[f.value for f in RedactableField]
    )
    _confirm(command)
    command.set_defaults(handler=redact.run_redact)


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


def _select(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("project selection")
    group.add_argument("--project", metavar="NAME", help=PROJECT_HELP)


def _confirm(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("confirmation")
    group.add_argument(
        "--yes", action="store_true", help="apply without asking (needed without a TTY)"
    )


def _depth(text: str) -> int:
    try:
        depth = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if not 0 <= depth <= MAX_DEPTH:
        raise argparse.ArgumentTypeError(f"expected 0 to {MAX_DEPTH}")
    return depth
