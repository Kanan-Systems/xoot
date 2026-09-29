"""SQL access for the session_item_ref table."""

import sqlite3
from datetime import datetime

from xoot.models.fields import format_timestamp
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_item_ref import SessionItemRef


def link(
    conn: sqlite3.Connection,
    project_id: int,
    session_id: int,
    item_id: int,
    linked_at: datetime,
) -> bool:
    """
    Link an item to a session unless it is already linked.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project of both the session and the item.
        - session_id (int): session id.
        - item_id (int): item id.
        - linked_at (datetime): link time.

    Returns:
        - created (bool): True when a new link was stored.
    """
    cursor = conn.execute(
        "INSERT INTO session_item_ref (session_id, item_id, project_id, linked_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (session_id, item_id) DO NOTHING",
        (session_id, item_id, project_id, format_timestamp(linked_at)),
    )
    return cursor.rowcount == 1


def list_for_session(conn: sqlite3.Connection, session_id: int) -> list[SessionItemRef]:
    """
    List a session's links, oldest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - session_id (int): session id.

    Returns:
        - refs (list[SessionItemRef]): the links.
    """
    rows = conn.execute(
        "SELECT session_id, item_id, project_id, linked_at, disposition "
        "FROM session_item_ref WHERE session_id = ? ORDER BY linked_at, item_id",
        (session_id,),
    ).fetchall()
    return [SessionItemRef.model_validate(dict(row)) for row in rows]


def set_disposition(
    conn: sqlite3.Connection, session_id: int, item_id: int, disposition: Disposition
) -> None:
    """
    Record what happened to a linked item at session close.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - session_id (int): session id.
        - item_id (int): item id.
        - disposition (Disposition): the chosen disposition.
    """
    conn.execute(
        "UPDATE session_item_ref SET disposition = ? WHERE session_id = ? AND item_id = ?",
        (disposition.value, session_id, item_id),
    )


def open_session_ids(conn: sqlite3.Connection, item_id: int) -> list[int]:
    """
    List the open sessions an item is linked to.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): item id.

    Returns:
        - session_ids (list[int]): ascending ids.
    """
    rows = conn.execute(
        "SELECT session.id FROM session_item_ref "
        "JOIN session ON session.id = session_item_ref.session_id "
        "WHERE session_item_ref.item_id = ? AND session.status = 'open' "
        "ORDER BY session.id",
        (item_id,),
    ).fetchall()
    return [int(row[0]) for row in rows]


def count_by_session(conn: sqlite3.Connection, project_id: int) -> dict[int, int]:
    """
    Count each session's linked items across a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - counts (dict[int, int]): session id to link count; sessions with
          no links are absent.
    """
    rows = conn.execute(
        "SELECT session_id, count(*) FROM session_item_ref "
        "WHERE project_id = ? GROUP BY session_id",
        (project_id,),
    ).fetchall()
    return {int(row[0]): int(row[1]) for row in rows}
