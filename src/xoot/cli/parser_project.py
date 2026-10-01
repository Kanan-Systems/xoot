"""The `xoot project` subcommands and `xoot backlog`."""

import argparse
from collections.abc import Callable

from xoot.cli.commands import backlog, project
from xoot.cli.commands.common import ALIAS_HINT
from xoot.cli.parser_options import confirm, select


def add_project(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    """
    Add `xoot project` and its actions.

    Args:
        - commands (argparse._SubParsersAction): the top-level subparsers.
        - common (argparse.ArgumentParser): the shared --db/--json parent.
    """
    group = commands.add_parser(
        "project",
        help="list, show and rename projects; add or remove aliases and paths",
    )
    actions = group.add_subparsers(dest="action", required=True, metavar="ACTION")
    listing = actions.add_parser("list", parents=[common], help="list every project")
    listing.set_defaults(handler=project.run_list)
    show = actions.add_parser("show", parents=[common], help="show one project")
    select(show)
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
        select(action)
        if confirmed:
            confirm(action)
        action.set_defaults(handler=handler)
    _rename(actions, common)


def _rename(
    actions: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    rename = actions.add_parser(
        "rename",
        parents=[common],
        help="rename a project (never its key prefix)",
        epilog=ALIAS_HINT,
    )
    # The project is named once: positionally or with --project.
    rename.add_argument(
        "target",
        nargs="?",
        metavar="PROJECT",
        help="project alias or key prefix (or pass --project)",
    )
    select(rename, "project alias or key prefix (instead of PROJECT)")
    group = rename.add_argument_group("rename")
    group.add_argument("--name", help="the new display name")
    group.add_argument("--alias", help="an alias to add, e.g. the new name as a slug")
    confirm(rename)
    rename.set_defaults(handler=project.run_rename, refine=_one_project(rename))


def _one_project(
    parser: argparse.ArgumentParser,
) -> Callable[[argparse.Namespace], None]:
    """
    Require the project exactly once, as PROJECT or --project, and store it
    in args.project; otherwise a usage error, before any database opens.
    """

    def refine(args: argparse.Namespace) -> None:
        named = {name for name in (args.target, args.project) if name is not None}
        if len(named) != 1:
            parser.error("name the project once: PROJECT or --project")
        args.project = named.pop()

    return refine


def add_backlog(
    commands: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    """
    Add `xoot backlog`, the read-only backlog list.

    Args:
        - commands (argparse._SubParsersAction): the top-level subparsers.
        - common (argparse.ArgumentParser): the shared --db/--json parent.
    """
    command = commands.add_parser(
        "backlog", parents=[common], help="list the open backlog (read-only)"
    )
    select(command)
    group = command.add_argument_group("backlog")
    group.add_argument(
        "--at",
        metavar="KEY",
        help="a goal or batch key (or <prefix>:<key>): only its own backlog",
    )
    group.add_argument(
        "--all", action="store_true", help="include done and dropped backlog items"
    )
    command.set_defaults(handler=backlog.run_backlog)
