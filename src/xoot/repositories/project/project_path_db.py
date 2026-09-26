"""SQL access for the project_path table."""

import sqlite3
from collections.abc import Sequence

from xoot.models.project.project_path import ProjectPath


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
    return None if row is None else ProjectPath.model_validate(dict(row))


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
    return None if row is None else ProjectPath.model_validate(dict(row))
