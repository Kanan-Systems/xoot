"""
Running database work from async tools.

Each call runs on an AnyIO worker thread with its own Store, opened and
closed on that thread. sqlite3 connections refuse use from a thread other
than their creator, and worker threads are pooled, so nothing is shared.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path

import anyio.to_thread
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from xoot.exceptions.xoot_error import XootError
from xoot.server.errors import safe_message
from xoot.server.xoot_server import XootServer
from xoot.store.store import Store


def db_path_of(ctx: Context) -> Path:
    """
    Return the database file of the server handling a request.

    Args:
        - ctx (Context): the tool's request context.

    Returns:
        - path (Path): the server's database file.

    Raises:
        - TypeError: the context belongs to another server class.
    """
    server = ctx.mcp_server
    if not isinstance(server, XootServer):
        raise TypeError("xoot tools must run on an XootServer")
    return server.db_path


async def run_db[T](ctx: Context, work: Callable[[Store], T]) -> T:
    """
    Run work against a fresh Store on a worker thread.

    Args:
        - ctx (Context): the tool's request context.
        - work (Callable[[Store], T]): the database work.

    Returns:
        - result (T): what work returned.

    Raises:
        - ToolError: work raised a domain or validation error; the message is
          the safe form, the original is chained.
    """
    return await anyio.to_thread.run_sync(partial(_in_store, db_path_of(ctx), work))


def _in_store[T](db_path: Path, work: Callable[[Store], T]) -> T:
    try:
        store = Store.open(db_path)
        try:
            return work(store)
        finally:
            store.close()
    except (XootError, ValidationError) as exc:
        raise ToolError(safe_message(exc)) from exc
