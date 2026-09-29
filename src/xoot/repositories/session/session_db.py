"""SQL access for the session table."""

import sqlite3

from xoot.models.session.new_session import NewSession
from xoot.models.session.session import Session
from xoot.models.session.session_status import SessionStatus

_COLUMNS = (
    "id, project_id, number, client, title, status, summary, start_seq, "
    "close_seq, started_at, closed_at"
)


def insert(conn: sqlite3.Connection, new: NewSession) -> Session:
    """
    Insert an open session.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewSession): the validated row values.

    Returns:
        - session (Session): the stored row.
    """
    row = conn.execute(
        "INSERT INTO session (project_id, number, client, title, status, "
        "start_seq, started_at) VALUES (:project_id, :number, :client, :title, "
        "'open', :start_seq, :started_at) "
        f"RETURNING {_COLUMNS}",
        new.model_dump(mode="json"),
    ).fetchone()
    return Session.model_validate(dict(row))


def get(conn: sqlite3.Connection, session_id: int) -> Session | None:
    """
    Fetch a session by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - session_id (int): session id.

    Returns:
        - session (Session | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM session WHERE id = ?", (session_id,)
    ).fetchone()
    return None if row is None else Session.model_validate(dict(row))


def get_by_number(
    conn: sqlite3.Connection, project_id: int, number: int
) -> Session | None:
    """
    Fetch a session by its number within a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - number (int): the per-project session number.

    Returns:
        - session (Session | None): the session, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM session WHERE project_id = ? AND number = ?",
        (project_id, number),
    ).fetchone()
    return None if row is None else Session.model_validate(dict(row))


def list_open(conn: sqlite3.Connection, project_id: int, limit: int) -> list[Session]:
    """
    List a project's open sessions, oldest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - limit (int): the most rows to return.

    Returns:
        - sessions (list[Session]): up to limit open sessions.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM session WHERE project_id = ? AND status = 'open' "
        "ORDER BY number LIMIT ?",
        (project_id, limit),
    ).fetchall()
    return [Session.model_validate(dict(row)) for row in rows]


def list_for_project(
    conn: sqlite3.Connection,
    project_id: int,
    status: SessionStatus | None,
    limit: int,
) -> list[Session]:
    """
    List a project's sessions, open ones first, then newest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - status (SessionStatus | None): only this status; any when None.
        - limit (int): the most rows to return.

    Returns:
        - sessions (list[Session]): up to limit sessions.
    """
    value = None if status is None else status.value
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM session WHERE project_id = ? "
        "AND (? IS NULL OR status = ?) "
        "ORDER BY status = 'open' DESC, number DESC LIMIT ?",
        (project_id, value, value, limit),
    ).fetchall()
    return [Session.model_validate(dict(row)) for row in rows]


def list_for_item(conn: sqlite3.Connection, item_id: int) -> list[Session]:
    """
    List the sessions an item is linked to, by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): item id.

    Returns:
        - sessions (list[Session]): the linked sessions.
    """
    columns = ", ".join(f"session.{name.strip()}" for name in _COLUMNS.split(","))
    rows = conn.execute(
        f"SELECT {columns} FROM session "
        "JOIN session_item_ref ON session_item_ref.session_id = session.id "
        "WHERE session_item_ref.item_id = ? ORDER BY session.number",
        (item_id,),
    ).fetchall()
    return [Session.model_validate(dict(row)) for row in rows]


def next_number(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Return the next session number of a project.

    Safe only inside a write transaction, which serializes allocators.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.

    Returns:
        - number (int): one past the highest session number.
    """
    row = conn.execute(
        "SELECT coalesce(max(number), 0) + 1 FROM session WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return int(row[0])


def update(conn: sqlite3.Connection, session: Session) -> None:
    """
    Write a session's mutable columns: status, summary, close_seq and
    closed_at, plus title, which only a redaction changes.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - session (Session): the new row values.
    """
    conn.execute(
        "UPDATE session SET title = :title, status = :status, "
        "summary = :summary, close_seq = :close_seq, closed_at = :closed_at "
        "WHERE id = :id",
        session.model_dump(mode="json"),
    )
