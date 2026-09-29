"""`xoot brief` and `xoot tree`: the project read views."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import project_of
from xoot.cli.console import Console
from xoot.cli.render.brief import render_brief
from xoot.cli.render.tree import render_tree
from xoot.models.item.tree_query import TreeQuery
from xoot.server.brief import build_brief
from xoot.server.key_book import KeyBook
from xoot.server.render import tree_entries
from xoot.server.schemas.tree_output import TreeOutput
from xoot.services.key_resolver import item_by_key
from xoot.services.project_scope import unqualified
from xoot.services.tree_service import tree
from xoot.store.store import Store


def run_brief(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print the brief of the resolved project.

    Args:
        - args (argparse.Namespace): the optional --project.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
    """
    project, resolved_by = project_of(args, store)
    with store.read() as conn:
        brief = build_brief(conn, project, resolved_by, store.path)
    console.result(brief, render_brief)
    return exit_codes.OK


def run_tree(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print the item tree of the resolved project.

    Args:
        - args (argparse.Namespace): --project, --root (qualified or not),
          --depth and --all.
        - store (Store): the database.
        - console (Console): output; a truncated tree adds a warning.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - NotFoundError: --root names no item.
        - QualifierError: --root names another project than --project.
    """
    project, resolved_by = project_of(args, store, [args.root])
    with store.read() as conn:
        root_id = (
            None
            if args.root is None
            else item_by_key(conn, project.id, unqualified(args.root)).id
        )
    query = TreeQuery(root_id=root_id, depth=args.depth, include_terminal=args.all)
    result = tree(store, project.id, query)
    with store.read() as conn:
        nodes = tree_entries(KeyBook(conn), result)
    output = TreeOutput(
        project=project.key_prefix,
        resolved_by=resolved_by,
        nodes=nodes,
        truncated=result.truncated,
    )
    console.result(output, render_tree)
    if output.truncated:
        console.warn("the tree was truncated by --depth or the item limit")
    return exit_codes.OK
