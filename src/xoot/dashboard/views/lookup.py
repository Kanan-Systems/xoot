"""Public keys and prefixes from a URL, resolved to rows or a 404."""

import sqlite3
from collections.abc import Callable

from xoot.dashboard.errors import not_found
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.services import key_resolver


def project_of(conn: sqlite3.Connection, prefix: str) -> Project:
    """
    Resolve a URL's project prefix.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the prefix from the path.

    Returns:
        - project (Project): the project.

    Raises:
        - ApiError: 404, the prefix names no project.
    """
    return _resolve(key_resolver.project_by_key, conn, prefix)


def item_of(conn: sqlite3.Connection, key: str) -> Item:
    """
    Resolve a URL's item key.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - key (str): the key from the path.

    Returns:
        - item (Item): the item.

    Raises:
        - ApiError: 404, the key names no item.
    """
    return _resolve(key_resolver.item_by_key, conn, key)


def session_in(conn: sqlite3.Connection, project: Project, key: str) -> Session:
    """
    Resolve a URL's session key within the URL's project.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project (Project): the project the path names.
        - key (str): the session key from the path.

    Returns:
        - session (Session): the session.

    Raises:
        - ApiError: 404, the key names no session of this project.
    """
    session = _resolve(key_resolver.session_by_key, conn, key)
    if session.project_id != project.id:
        raise not_found(key)
    return session


def _resolve[T](
    lookup: Callable[[sqlite3.Connection, str], T], conn: sqlite3.Connection, key: str
) -> T:
    try:
        return lookup(conn, key)
    except NotFoundError as exc:
        raise not_found(key) from exc
