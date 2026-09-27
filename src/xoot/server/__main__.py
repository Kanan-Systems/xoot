"""
Entry point for `xoot-mcp` and `python -m xoot.server`: serve MCP over stdio.

stdout carries only protocol messages, so every log line goes to stderr.
SIGINT and SIGTERM stop the server quietly, as closing stdin does.
"""

import argparse
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

import anyio
import anyio.abc

from xoot.server.app import build_server
from xoot.server.xoot_server import XootServer
from xoot.store.paths import default_db_path

LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"
# Bounded so a signal always ends the process within two seconds.
DRAIN_S = 1.5
DRAIN_POLL_S = 0.02


def main(argv: Sequence[str] | None = None) -> None:
    """
    Parse arguments, log the database path once and serve until stdin closes
    or SIGINT or SIGTERM arrives.

    Args:
        - argv (Sequence[str] | None): arguments; sys.argv[1:] when None.
    """
    args = _parser().parse_args(argv)
    db_path = default_db_path() if args.db is None else _absolute(args.db)
    _configure_logging()
    logging.getLogger("xoot.server").info("database: %s", db_path)
    anyio.run(_serve, build_server(db_path))


async def _serve(server: XootServer) -> None:
    async with anyio.create_task_group() as group:
        # start(), not start_soon(): the handlers are in place before serving.
        await group.start(_stop_on_signal, server, group.cancel_scope)
        await server.run_stdio_async()
        group.cancel_scope.cancel()


async def _stop_on_signal(
    server: XootServer,
    scope: anyio.CancelScope,
    *,
    task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
) -> None:
    # Replaces the default handlers, which print a KeyboardInterrupt
    # traceback on SIGINT and kill the process mid-write on SIGTERM.
    with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
        task_status.started()
        async for signum in signals:
            logger = logging.getLogger("xoot.server")
            logger.info("stopping on %s", signal.Signals(signum).name)
            scope.cancel()
            if not await _drained(server):
                logger.warning("stopping with a database call still running")
            sys.stderr.flush()
            # The SDK reads stdin on a non-daemon worker thread that no
            # cancellation reaches, so returning would wait for more input.
            os._exit(0)


async def _drained(server: XootServer) -> bool:
    # Cancelled tool calls still wait for their worker thread, so the count
    # falls as each transaction commits or rolls back.
    with anyio.move_on_after(DRAIN_S, shield=True):
        while server.db_calls:
            await anyio.sleep(DRAIN_POLL_S)
    return server.db_calls == 0


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
