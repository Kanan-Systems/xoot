"""
Entry point for `xoot-mcp` and `python -m xoot.server`: serve MCP over stdio.

stdout carries only protocol messages, so every log line goes to stderr.
"""

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from xoot.server.app import build_server
from xoot.store.paths import default_db_path

LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"


def main(argv: Sequence[str] | None = None) -> None:
    """
    Parse arguments, log the database path once and serve until stdin closes.

    Args:
        - argv (Sequence[str] | None): arguments; sys.argv[1:] when None.
    """
    args = _parser().parse_args(argv)
    db_path = default_db_path() if args.db is None else _absolute(args.db)
    _configure_logging()
    logging.getLogger("xoot.server").info("database: %s", db_path)
    build_server(db_path).run()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xoot-mcp", description="Serve the xoot tracker over MCP stdio."
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help="database file (default: $XDG_DATA_HOME/xoot/xoot.db)",
    )
    return parser


def _absolute(path: str) -> Path:
    # abspath, not resolve(): following a symlink here would hide it from
    # the store's symlink refusal.
    return Path(os.path.abspath(os.path.expanduser(path)))


def _configure_logging() -> None:
    # Configured before the server exists, so the SDK's own basicConfig call
    # finds a handler and leaves this one in place.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=LOG_FORMAT)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("xoot").setLevel(logging.INFO)


if __name__ == "__main__":
    main()
