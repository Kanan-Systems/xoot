"""
Session reads: listing a project's sessions and following session-item
links in both directions.

Functions take a connection inside the caller's read transaction.
"""

import sqlite3

from xoot.models.session.session import Session
from xoot.models.session.session_link import SessionLink
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.event import event_db
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


def session_links(conn: sqlite3.Connection, session_id: int) -> list[SessionLink]:
    """
    Return a session's linked items with their dispositions, in link order.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - session_id (int): the session id.

    Returns:
        - links (list[SessionLink]): a link to a missing item is skipped.

    Raises:
        - InvalidIdError: session_id is not an int id.
    """
    check_id("session_id", session_id)
    captured = event_db.created_in_session_backlog(conn, session_id)
    links = []
    for ref in session_item_ref_db.list_for_session(conn, session_id):
        item = item_db.get(conn, ref.item_id)
        if item is not None:
            links.append(
                SessionLink(
                    item=item,
                    disposition=ref.disposition,
                    captured=item.id in captured,
                )
            )
    return links


def linked_counts(conn: sqlite3.Connection, project_id: int) -> dict[int, int]:
    """
    Count the items each session of a project is linked to.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.

    Returns:
        - counts (dict[int, int]): session id to count; absent means none.

    Raises:
        - InvalidIdError: project_id is not an int id.
    """
    check_id("project_id", project_id)
    return session_item_ref_db.count_by_session(conn, project_id)


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
