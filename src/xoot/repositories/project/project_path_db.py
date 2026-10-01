"""SQL access for the project_path table."""

import sqlite3
from collections.abc import Sequence

from xoot.models.project.project_path import ProjectPath
from xoot.repositories.stored_row import from_row


def insert(conn: sqlite3.Connection, path: str, project_id: int) -> ProjectPath:
    """
    Register a directory for a project.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - path (str): absolute, normalized path.
        - project_id (int): project id.

    Returns:
        - path (ProjectPath): the stored row.
    """
    conn.execute(
        "INSERT INTO project_path (path, project_id) VALUES (?, ?)",
        (path, project_id),
    )
    return ProjectPath(path=path, project_id=project_id)


def get(conn: sqlite3.Connection, path: str) -> ProjectPath | None:
    """
    Fetch a registered path by exact value.

    Args:
        - conn (sqlite3.Connection): open connection.
        - path (str): normalized path.

    Returns:
        - path (ProjectPath | None): the row, or None.
    """
    row = conn.execute(
        "SELECT path, project_id FROM project_path WHERE path = ?", (path,)
    ).fetchone()
    return None if row is None else from_row(ProjectPath, "project_path", row)


def longest_of(
    conn: sqlite3.Connection, candidates: Sequence[str]
) -> ProjectPath | None:
    """
    Return the longest registered path among exact candidates.

    Matching exact candidates (the caller passes whole-segment ancestors)
    rather than using LIKE keeps /a/xoot from matching /a/xoot2.

    Args:
        - conn (sqlite3.Connection): open connection.
        - candidates (Sequence[str]): normalized paths to try.

    Returns:
        - path (ProjectPath | None): the longest registered one, or None.
    """
    if not candidates:
        return None
    # Only "?" placeholders are generated; the values stay bound parameters.
    placeholders = ", ".join("?" for _ in candidates)
    row = conn.execute(
        f"SELECT path, project_id FROM project_path WHERE path IN ({placeholders}) "
        "ORDER BY length(path) DESC LIMIT 1",
        tuple(candidates),
    ).fetchone()
    return None if row is None else from_row(ProjectPath, "project_path", row)


def list_for_project(conn: sqlite3.Connection, project_id: int) -> list[str]:
    """
    List one project's paths, in order.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - paths (list[str]): the project's normalized paths.
    """
    rows = conn.execute(
        "SELECT path FROM project_path WHERE project_id = ? ORDER BY path",
        (project_id,),
    ).fetchall()
    return [row[0] for row in rows]


def delete(conn: sqlite3.Connection, path: str, project_id: int) -> bool:
    """
    Remove a path from a project.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - path (str): the normalized path.
        - project_id (int): the project it must belong to.

    Returns:
        - deleted (bool): False when the project has no such path.
    """
    cursor = conn.execute(
        "DELETE FROM project_path WHERE path = ? AND project_id = ?",
        (path, project_id),
    )
    return cursor.rowcount == 1
