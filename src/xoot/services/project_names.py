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
from xoot.services.lookups import require_project


def require_free_prefix(conn: sqlite3.Connection, prefix: str) -> None:
    """
    Refuse a new key prefix that already names a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - prefix (str): the validated prefix.

    Raises:
        - DuplicateError: a project has this prefix or this alias; the
          message names that project.
    """
    _refuse_taken(conn, "key_prefix", prefix, None)


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
        - DuplicateError: the alias is taken, or is another project's prefix;
          the message names that project.
    """
    _refuse_taken(conn, "alias", alias, project_id)


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


def _refuse_taken(
    conn: sqlite3.Connection, field: str, name: str, own_project_id: int | None
) -> None:
    """Raise DuplicateError naming the project a name already belongs to."""
    owner = project_db.get_by_prefix(conn, name)
    if owner is not None and owner.id != own_project_id:
        raise DuplicateError(field, name, f"the prefix of project {owner.key_prefix}")
    alias = project_alias_db.get(conn, name)
    if alias is not None:
        holder = require_project(conn, alias.project_id).key_prefix
        raise DuplicateError(field, name, f"an alias of project {holder}")
