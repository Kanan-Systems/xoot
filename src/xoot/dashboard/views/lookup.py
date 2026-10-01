"""
Public keys and project names from a URL, resolved to rows or a 404.

A URL's project segment is a key prefix or an alias, resolved by the same
rule as the MCP project argument (prefix first, then alias; the two share
one namespace, so they never collide).
"""

import sqlite3
from collections.abc import Callable

from xoot.dashboard.errors import not_found
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision import Decision
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.services import key_resolver
from xoot.services.project_resolver import by_name


def project_of(conn: sqlite3.Connection, prefix: str) -> Project:
    """
    Resolve a URL's project segment: a key prefix or an alias.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the prefix or alias from the path.

    Returns:
        - project (Project): the project.

    Raises:
        - ApiError: 404, the segment names no project.
    """
    found = by_name(conn, prefix)
    if found is None:
        raise not_found(prefix)
    return found[0]


def item_of(conn: sqlite3.Connection, project: Project, key: str) -> Item:
    """
    Resolve a URL's item key within the URL's project; old keys resolve too.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project (Project): the project the path names.
        - key (str): the unqualified key from the path, slashes included.

    Returns:
        - item (Item): the item.

    Raises:
        - ApiError: 404, the key names no item of this project.
    """
    return _resolve(key_resolver.item_by_key, conn, project, key)


def decision_of(conn: sqlite3.Connection, project: Project, key: str) -> Decision:
    """
    Resolve a URL's decision key within the URL's project.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project (Project): the project the path names.
        - key (str): the unqualified key from the path, slashes included.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - ApiError: 404, the key names no decision of this project.
    """
    return _resolve(key_resolver.decision_by_key, conn, project, key)


def _resolve[T](
    lookup: Callable[[sqlite3.Connection, int, str], T],
    conn: sqlite3.Connection,
    project: Project,
    key: str,
) -> T:
    try:
        return lookup(conn, project.id, key)
    except NotFoundError as exc:
        raise not_found(key) from exc
