"""`xoot backlog`: the backlog list, read-only, as backlog_list shows it."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import project_of
from xoot.cli.console import Console
from xoot.cli.render.backlog import render_backlog
from xoot.server.backlog_listing import backlog_output
from xoot.services.key_resolver import item_by_key
from xoot.services.project_scope import unqualified
from xoot.store.store import Store


def run_backlog(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print the open backlog of the resolved project, or of one goal or batch.

    Args:
        - args (argparse.Namespace): --project, --at (qualified or not) and
          --all.
        - store (Store): the database.
        - console (Console): output; a capped list adds a warning.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - NotFoundError: --at names no item.
        - QualifierError: --at names another project than --project.
    """
    project, resolved_by = project_of(args, store, [args.at])
    with store.read() as conn:
        target = (
            None
            if args.at is None
            else item_by_key(conn, project.id, unqualified(args.at))
        )
        output = backlog_output(conn, project, resolved_by, target, args.all)
    console.result(output, render_backlog)
    if output.truncated:
        console.warn("the list was capped at 100 items; narrow it with --at")
    return exit_codes.OK
