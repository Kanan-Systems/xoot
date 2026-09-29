"""
Resolving public keys to rows, with no dependency on the MCP server.

Keys are resolved within one project and are unqualified here; callers
split off a "<prefix>:" qualifier first (see project_scope). An item key
that is no longer live resolves through item_alias, so every key an item
ever held still finds it; a decision key resolves through its owner, so it
follows the owner's moves too.

A well-formed key that names nothing, and a malformed one, both raise
NotFoundError. Only a well-formed key is kept on the error: it holds nothing
but [a-z0-9/:-], while other text is arbitrary input.
"""

import sqlite3

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision import Decision
from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_alias_db, item_db
from xoot.repositories.project import project_db
from xoot.utils.keys import (
    PREFIX_KEY,
    is_key,
    parse_decision_key,
    parse_item_key,
)

MALFORMED = "malformed key"


def item_by_key(conn: sqlite3.Connection, project_id: int, key: str) -> Item:
    """
    Fetch an item by its current key or any key it held before a move.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project_id (int): the project the key belongs to.
        - key (str): the unqualified key as the caller sent it.

    Returns:
        - item (Item): the item.

    Raises:
        - NotFoundError: the key is malformed or names no item.
    """
    item = None
    if parse_item_key(key) is not None:
        item = item_db.get_by_key(conn, project_id, key)
        if item is None:
            item_id = item_alias_db.item_id_for(conn, project_id, key)
            item = None if item_id is None else item_db.get(conn, item_id)
    if item is None:
        raise NotFoundError("item", safe_ref(key))
    return item


def decision_by_key(conn: sqlite3.Connection, project_id: int, key: str) -> Decision:
    """
    Fetch a decision by key: its owner's key (current or old) and number.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project_id (int): the project the key belongs to.
        - key (str): the unqualified key as the caller sent it.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - NotFoundError: the key is malformed or names no decision.
    """
    parts = parse_decision_key(key)
    decision = None
    if parts is not None:
        owner_key, number = parts
        try:
            owner = item_by_key(conn, project_id, owner_key)
        except NotFoundError:
            owner = None
        if owner is not None:
            decision = decision_db.get_by_owner(conn, owner.id, number)
    if decision is None:
        raise NotFoundError("decision", safe_ref(key))
    return decision


def project_by_key(conn: sqlite3.Connection, prefix: str) -> Project:
    """
    Fetch a project by its key prefix, the public key of a project.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - prefix (str): the prefix as the caller sent it.

    Returns:
        - project (Project): the project.

    Raises:
        - NotFoundError: no project has that prefix.
    """
    well_formed = PREFIX_KEY.fullmatch(prefix) is not None
    project = project_db.get_by_prefix(conn, prefix) if well_formed else None
    if project is None:
        raise NotFoundError("project", prefix if well_formed else MALFORMED)
    return project


def entity_by_key(
    conn: sqlite3.Connection, project_id: int, key: str
) -> tuple[EntityType, int]:
    """
    Resolve an item or decision key of one project.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project_id (int): the project the key belongs to.
        - key (str): the unqualified key as the caller sent it.

    Returns:
        - entity (tuple[EntityType, int]): the entity type and row id.

    Raises:
        - NotFoundError: the key names nothing.
    """
    if parse_decision_key(key) is not None:
        return EntityType.DECISION, decision_by_key(conn, project_id, key).id
    return EntityType.ITEM, item_by_key(conn, project_id, key).id


def safe_ref(key: str) -> str:
    """
    Return a key fit to echo in an error: itself if well-formed.

    Args:
        - key (str): the key as the caller sent it.

    Returns:
        - ref (str): the key, or "malformed key".
    """
    return key if is_key(key) else MALFORMED
