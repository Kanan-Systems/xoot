"""
Resolving public keys to rows, with no dependency on the MCP server.

A well-formed key that names nothing, and a malformed one, both raise
NotFoundError. Only a well-formed key is kept on the error: it can hold
nothing but [a-z0-9-] and digits, while other text is arbitrary input.
"""

import sqlite3

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision import Decision
from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.session import session_db
from xoot.utils.keys import (
    DECISION_KEY,
    ITEM_KEY,
    PREFIX_KEY,
    SESSION_KEY,
    is_key,
    parse_key,
)

MALFORMED = "malformed key"


def item_by_key(conn: sqlite3.Connection, key: str) -> Item:
    """
    Fetch an item by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - item (Item): the item.

    Raises:
        - NotFoundError: the key is malformed or names no item.
    """
    item = None if parse_key(ITEM_KEY, key) is None else item_db.get_by_key(conn, key)
    if item is None:
        raise NotFoundError("item", safe_ref(key))
    return item


def decision_by_key(conn: sqlite3.Connection, key: str) -> Decision:
    """
    Fetch a decision by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - NotFoundError: the key is malformed or names no decision.
    """
    decision = (
        None
        if parse_key(DECISION_KEY, key) is None
        else decision_db.get_by_key(conn, key)
    )
    if decision is None:
        raise NotFoundError("decision", safe_ref(key))
    return decision


def session_by_key(conn: sqlite3.Connection, key: str) -> Session:
    """
    Fetch a session by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - session (Session): the session.

    Raises:
        - NotFoundError: the key is malformed or names no session.
    """
    parts = parse_key(SESSION_KEY, key)
    project = None if parts is None else project_db.get_by_prefix(conn, parts[0])
    session = (
        None
        if parts is None or project is None
        else session_db.get_by_number(conn, project.id, parts[1])
    )
    if session is None:
        raise NotFoundError("session", safe_ref(key))
    return session


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


def entity_by_key(conn: sqlite3.Connection, key: str) -> tuple[EntityType, int]:
    """
    Resolve any public key: an item, decision or session key, or a prefix.

    A prefix may itself look like an item key ("ab-12"), so a record key is
    tried first and the prefix only when no record matches.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - entity (tuple[EntityType, int]): the entity type and row id.

    Raises:
        - NotFoundError: the key names nothing.
    """
    lookups = (
        (EntityType.ITEM, item_by_key),
        (EntityType.DECISION, decision_by_key),
        (EntityType.SESSION, session_by_key),
        (EntityType.PROJECT, project_by_key),
    )
    for entity_type, lookup in lookups:
        try:
            return entity_type, lookup(conn, key).id
        except NotFoundError:
            continue
    raise NotFoundError("record", safe_ref(key))


def safe_ref(key: str) -> str:
    """
    Return a key fit to echo in an error: itself if well-formed.

    Args:
        - key (str): the key as the caller sent it.

    Returns:
        - ref (str): the key, or "malformed key".
    """
    return key if is_key(key) else MALFORMED
