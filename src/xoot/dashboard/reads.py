"""
Running a dashboard read on a worker thread with its own Store.

sqlite3 connections refuse use from a thread other than their creator and
worker threads are pooled, so each request opens a Store on the thread that
uses it and closes it before the response is built, as the MCP server does.
"""

import sqlite3
from collections.abc import Callable
from functools import partial
from pathlib import Path

import anyio.to_thread
from pydantic import BaseModel, ValidationError

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.errors import UNAVAILABLE, from_exception
from xoot.exceptions.xoot_error import XootError
from xoot.store.store import Store


async def run_read[M: BaseModel](
    db_path: Path, work: Callable[[sqlite3.Connection], M]
) -> M:
    """
    Run work inside one read transaction of a fresh Store.

    Args:
        - db_path (Path): the database file.
        - work (Callable[[sqlite3.Connection], M]): builds the response model
          from a connection inside the read snapshot.

    Returns:
        - model (M): what work returned.

    Raises:
        - ApiError: work, or opening the store, failed; the body is safe.
    """
    return await anyio.to_thread.run_sync(partial(_in_store, db_path, work))


def _in_store[M: BaseModel](
    db_path: Path, work: Callable[[sqlite3.Connection], M]
) -> M:
    try:
        store = Store.open(db_path)
        try:
            with store.read() as conn:
                return work(conn)
        finally:
            store.close()
    except (XootError, ValidationError) as exc:
        raise from_exception(exc) from exc
    except OSError as exc:
        raise ApiError(
            UNAVAILABLE, type(exc).__name__, "the database could not be opened"
        ) from exc
