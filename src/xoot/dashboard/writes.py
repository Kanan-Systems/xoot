"""
Running a dashboard write on a worker thread with its own Store.

Like a read, each write opens a Store on the thread that uses it and closes
it before the response is built. The work gets the Store itself, because the
services own their transactions (a two-phase write previews and applies in
separate ones). Every write is recorded as the user, through the dashboard.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path

import anyio.to_thread
from pydantic import BaseModel, ValidationError

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.write_errors import UNAVAILABLE, write_error
from xoot.exceptions.xoot_error import XootError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.store.store import Store

DASHBOARD = WriteContext(actor=Actor(kind=ActorKind.USER, client=Client.DASHBOARD))


async def run_write[M: BaseModel](db_path: Path, work: Callable[[Store], M]) -> M:
    """
    Run work against a fresh Store.

    Args:
        - db_path (Path): the database file.
        - work (Callable[[Store], M]): performs the write and builds the
          response model.

    Returns:
        - model (M): what work returned.

    Raises:
        - ApiError: work, or opening the store, failed; the body is safe.
    """
    return await anyio.to_thread.run_sync(partial(_in_store, db_path, work))


def _in_store[M: BaseModel](db_path: Path, work: Callable[[Store], M]) -> M:
    try:
        with Store.open(db_path) as store:
            return work(store)
    except (XootError, ValidationError) as exc:
        raise write_error(exc) from exc
    except OSError as exc:
        raise ApiError(
            UNAVAILABLE, type(exc).__name__, "the database could not be opened"
        ) from exc
