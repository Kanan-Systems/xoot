"""SQL access for the project_alias table."""

import sqlite3

from xoot.models.project.project_alias import ProjectAlias


def insert(conn: sqlite3.Connection, alias: str, project_id: int) -> ProjectAlias:
    """
    Register an alias for a project.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - alias (str): validated slug.
        - project_id (int): project id.

    Returns:
        - alias (ProjectAlias): the stored row.
    """
    conn.execute(
        "INSERT INTO project_alias (alias, project_id) VALUES (?, ?)",
        (alias, project_id),
    )
    return ProjectAlias(alias=alias, project_id=project_id)


def get(conn: sqlite3.Connection, alias: str) -> ProjectAlias | None:
    """
    Fetch an alias by exact name.

    Args:
        - conn (sqlite3.Connection): open connection.
        - alias (str): the alias.

    Returns:
        - alias (ProjectAlias | None): the row, or None.
    """
    row = conn.execute(
        "SELECT alias, project_id FROM project_alias WHERE alias = ?", (alias,)
    ).fetchone()
    return None if row is None else ProjectAlias.model_validate(dict(row))


def list_all(conn: sqlite3.Connection) -> list[ProjectAlias]:
    """
    List every alias, by name.

    Args:
        - conn (sqlite3.Connection): open connection.

    Returns:
        - aliases (list[ProjectAlias]): all aliases.
    """
    rows = conn.execute(
        "SELECT alias, project_id FROM project_alias ORDER BY alias"
    ).fetchall()
    return [ProjectAlias.model_validate(dict(row)) for row in rows]
