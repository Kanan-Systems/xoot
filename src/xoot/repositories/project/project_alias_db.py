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


def list_for_project(conn: sqlite3.Connection, project_id: int) -> list[str]:
    """
    List one project's aliases, by name.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - aliases (list[str]): the project's aliases.
    """
    rows = conn.execute(
        "SELECT alias FROM project_alias WHERE project_id = ? ORDER BY alias",
        (project_id,),
    ).fetchall()
    return [row[0] for row in rows]


def delete(conn: sqlite3.Connection, alias: str, project_id: int) -> bool:
    """
    Remove an alias from a project.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - alias (str): the alias.
        - project_id (int): the project it must belong to.

    Returns:
        - deleted (bool): False when the project has no such alias.
    """
    cursor = conn.execute(
        "DELETE FROM project_alias WHERE alias = ? AND project_id = ?",
        (alias, project_id),
    )
    return cursor.rowcount == 1
