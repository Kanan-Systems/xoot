"""
The shared namespace of key prefixes and aliases, and the path registry.

Every prefix and alias must resolve to exactly one project. An alias may
repeat its own project's prefix, which is redundant but unambiguous; any
other clash is refused. The schema's triggers enforce the same rule, so
these checks give a clear error before the database has to.
"""

import sqlite3

from xoot.exceptions.duplicate_error import DuplicateError
from xoot.repositories.project import project_alias_db, project_db, project_path_db


def require_free_prefix(conn: sqlite3.Connection, prefix: str) -> None:
    """
    Refuse a new key prefix that already names a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - prefix (str): the validated prefix.

    Raises:
        - DuplicateError: a project has this prefix or this alias.
    """
    if project_db.get_by_prefix(conn, prefix) is not None:
        raise DuplicateError("key_prefix", prefix)
    if project_alias_db.get(conn, prefix) is not None:
        raise DuplicateError("key_prefix", prefix)


def require_free_alias(
    conn: sqlite3.Connection, alias: str, project_id: int | None
) -> None:
    """
    Refuse an alias that already names a project, other than as its own prefix.

    Args:
        - conn (sqlite3.Connection): open connection.
        - alias (str): the validated alias.
        - project_id (int | None): the project that will own it; None while
          that project is being registered and has no row yet.

    Raises:
        - DuplicateError: the alias is taken, or is another project's prefix.
    """
    if project_alias_db.get(conn, alias) is not None:
        raise DuplicateError("alias", alias)
    owner = project_db.get_by_prefix(conn, alias)
    if owner is not None and owner.id != project_id:
        raise DuplicateError("alias", alias)


def require_free_path(conn: sqlite3.Connection, path: str) -> None:
    """
    Refuse a path that is already registered.

    Args:
        - conn (sqlite3.Connection): open connection.
        - path (str): the normalized path.

    Raises:
        - DuplicateError: any project already has this path.
    """
    if project_path_db.get(conn, path) is not None:
        raise DuplicateError("path", path)
