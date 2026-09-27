"""SQL access for the project table."""

import sqlite3
from datetime import datetime

from xoot.models.fields import format_timestamp
from xoot.models.project.project import Project

_COLUMNS = (
    "id, key_prefix, name, next_item_number, next_decision_number, next_seq, "
    "active_workflow_id, created_at"
)


def insert(
    conn: sqlite3.Connection, key_prefix: str, name: str, created_at: datetime
) -> Project:
    """
    Insert a project with fresh counters and no workflow yet.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - key_prefix (str): validated slug.
        - name (str): validated display name.
        - created_at (datetime): creation time.

    Returns:
        - project (Project): the stored row.
    """
    row = conn.execute(
        f"INSERT INTO project (key_prefix, name, created_at) VALUES (?, ?, ?) "
        f"RETURNING {_COLUMNS}",
        (key_prefix, name, format_timestamp(created_at)),
    ).fetchone()
    return Project.model_validate(dict(row))


def get(conn: sqlite3.Connection, project_id: int) -> Project | None:
    """
    Fetch a project by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - project (Project | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    return None if row is None else Project.model_validate(dict(row))


def get_by_prefix(conn: sqlite3.Connection, key_prefix: str) -> Project | None:
    """
    Fetch a project by key prefix.

    Args:
        - conn (sqlite3.Connection): open connection.
        - key_prefix (str): the prefix.

    Returns:
        - project (Project | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM project WHERE key_prefix = ?", (key_prefix,)
    ).fetchone()
    return None if row is None else Project.model_validate(dict(row))


def set_active_workflow(
    conn: sqlite3.Connection, project_id: int, workflow_id: int
) -> Project:
    """
    Point a project at a workflow version.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.
        - workflow_id (int): a workflow of the same project.

    Returns:
        - project (Project): the updated row.
    """
    row = conn.execute(
        f"UPDATE project SET active_workflow_id = ? WHERE id = ? RETURNING {_COLUMNS}",
        (workflow_id, project_id),
    ).fetchone()
    return Project.model_validate(dict(row))


def set_name(conn: sqlite3.Connection, project_id: int, name: str) -> Project:
    """
    Replace a project's name. Only a redaction renames a project.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.
        - name (str): the new name.

    Returns:
        - project (Project): the stored row.
    """
    row = conn.execute(
        f"UPDATE project SET name = ? WHERE id = ? RETURNING {_COLUMNS}",
        (name, project_id),
    ).fetchone()
    return Project.model_validate(dict(row))


def allocate_item_number(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Take the next item number from the project counter.

    Must run inside the write transaction that uses the number, so the
    counter and the item commit or roll back together.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.

    Returns:
        - number (int): the allocated number.
    """
    return _allocate(
        conn,
        "UPDATE project SET next_item_number = next_item_number + 1 "
        "WHERE id = ? RETURNING next_item_number - 1",
        project_id,
    )


def allocate_decision_number(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Take the next decision number from the project counter.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.

    Returns:
        - number (int): the allocated number.
    """
    return _allocate(
        conn,
        "UPDATE project SET next_decision_number = next_decision_number + 1 "
        "WHERE id = ? RETURNING next_decision_number - 1",
        project_id,
    )


def allocate_seq(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Take the next value of the project's sequence counter.

    Orders session starts and closes without trusting the clock. Must run
    inside the write transaction that stores the value.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.

    Returns:
        - seq (int): the allocated sequence value.
    """
    return _allocate(
        conn,
        "UPDATE project SET next_seq = next_seq + 1 "
        "WHERE id = ? RETURNING next_seq - 1",
        project_id,
    )


def _allocate(conn: sqlite3.Connection, sql: str, project_id: int) -> int:
    row = conn.execute(sql, (project_id,)).fetchone()
    return int(row[0])
