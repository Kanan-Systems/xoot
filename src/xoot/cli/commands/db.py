"""`xoot db`: database statistics and maintenance."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.console import Console
from xoot.cli.render.stats import render_stats, render_vacuum
from xoot.cli.schemas.vacuum_output import VacuumOutput
from xoot.services.stats_service import db_stats
from xoot.store.store import Store

WAL_HINT = (
    "the database was rebuilt, but another client kept the WAL from being "
    "truncated; close clients such as xoot-mcp and retry"
)


def run_stats(_args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print page counts, file sizes and row counts.

    Args:
        - _args (argparse.Namespace): unused.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.
    """
    console.result(db_stats(store), render_stats)
    return exit_codes.OK


def run_vacuum(_args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Rebuild the database without free pages and report before and after.

    Args:
        - _args (argparse.Namespace): unused.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK, or UNAVAILABLE when the WAL was not truncated.

    Raises:
        - DatabaseBusyError: other connections kept the vacuum from running.
    """
    before = db_stats(store)
    checkpointed = store.vacuum()
    output = VacuumOutput(
        before=before, after=db_stats(store), checkpointed=checkpointed
    )
    console.result(output, render_vacuum)
    if not checkpointed:
        console.warn(WAL_HINT)
        return exit_codes.UNAVAILABLE
    return exit_codes.OK
