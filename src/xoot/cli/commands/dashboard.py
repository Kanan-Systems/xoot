"""`xoot dashboard`: serve the read-only web dashboard in the foreground."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.console import Console
from xoot.dashboard.runner import PortUnavailableError, bind, serve
from xoot.store.store import Store


def run_dashboard(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Serve the dashboard on 127.0.0.1 until Ctrl+C.

    Each request opens its own Store on the same file, so the store opened
    by the CLI is only used for its path.

    Args:
        - args (argparse.Namespace): --port and --open.
        - store (Store): the database, as chosen by --db.
        - console (Console): errors and warnings.

    Returns:
        - code (int): OK once stopped; UNAVAILABLE when the port cannot be
          bound.
    """
    try:
        sock = bind(args.port)
    except PortUnavailableError as exc:
        console.error(f"error: {exc.strerror}; pass --port to choose another")
        return exit_codes.UNAVAILABLE
    serve(store.path, sock, args.open)
    return exit_codes.OK
