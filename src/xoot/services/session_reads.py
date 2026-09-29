"""
Session reads: listing a project's sessions and following session-item
links in both directions.

Functions take a connection inside the caller's read transaction.
"""

import sqlite3

from xoot.models.session.session import Session
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.item import item_db
from xoot.repositories.session import session_db, session_item_ref_db
from xoot.services.id_checks import check_id


def list_sessions(
    conn: sqlite3.Connection,
    project_id: int,
    status: SessionStatus | None = None,
    limit: int = 100,
) -> list[Session]:
    """
    List a project's sessions, open ones first, then newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.
        - status (SessionStatus | None): only this status; any when None.
        - limit (int): the most sessions to return.

    Returns:
        - sessions (list[Session]): up to limit sessions.

    Raises:
        - InvalidIdError: project_id is not an int id.
    """
    check_id("project_id", project_id)
    return session_db.list_for_project(conn, project_id, status, limit)


def session_items(conn: sqlite3.Connection, session_id: int) -> list[str]:
    """
    Return the keys of the items a session is linked to, in link order.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - session_id (int): the session id.

    Returns:
        - keys (list[str]): item keys; a link to a missing item is skipped.

    Raises:
        - InvalidIdError: session_id is not an int id.
    """
    check_id("session_id", session_id)
    keys = []
    for ref in session_item_ref_db.list_for_session(conn, session_id):
        item = item_db.get(conn, ref.item_id)
        if item is not None:
            keys.append(item.key)
    return keys


def item_sessions(conn: sqlite3.Connection, item_id: int) -> list[Session]:
    """
    Return the sessions an item is linked to, by number.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - item_id (int): the item id.

    Returns:
        - sessions (list[Session]): the linked sessions.

    Raises:
        - InvalidIdError: item_id is not an int id.
    """
    check_id("item_id", item_id)
    return session_db.list_for_item(conn, item_id)
