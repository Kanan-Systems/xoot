"""
Session rules for writes: the session must be open and in the project, and
every item a write touches is linked to it.
"""

import sqlite3
from collections.abc import Iterable

from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.event.event_action import EventAction
from xoot.models.session.session import Session
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.session import session_item_ref_db
from xoot.services.lookups import require_session
from xoot.services.write_scope import WriteScope


def open_session_for(
    conn: sqlite3.Connection, project_id: int, session_id: int | None
) -> Session | None:
    """
    Validate the session a write carries, if any.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): the project being written.
        - session_id (int | None): the session from the write context.

    Returns:
        - session (Session | None): the open session, or None when the write
          carries none.

    Raises:
        - NotFoundError: no such session.
        - CrossProjectError: the session is in another project.
        - SessionStateError: the session is closed.
    """
    if session_id is None:
        return None
    session = require_session(conn, session_id, project_id)
    if session.status is not SessionStatus.OPEN:
        raise SessionStateError(f"session {session_id} is closed")
    return session


def scope_session_id(scope: WriteScope) -> int:
    """
    Return the session a scope is attributed to, for writes that need one.

    Args:
        - scope (WriteScope): the current write scope.

    Returns:
        - session_id (int): the scope's session id.

    Raises:
        - SessionStateError: the scope carries no session.
    """
    if scope.ctx.session_id is None:
        raise SessionStateError("this write needs a session")
    return scope.ctx.session_id


def link_items(
    scope: WriteScope, session: Session | None, item_ids: Iterable[int]
) -> None:
    """
    Link items to the write's session, recording each new link.

    Args:
        - scope (WriteScope): the current write scope.
        - session (Session | None): the open session, or None to do nothing.
        - item_ids (Iterable[int]): items touched by the write.
    """
    if session is None:
        return
    for item_id in item_ids:
        if session_item_ref_db.link(
            scope.conn, session.project_id, session.id, item_id, scope.now
        ):
            scope.noted(session, EventAction.LINK, {"item_id": item_id})
