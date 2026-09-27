"""
Resolving what a tool call names: public keys to rows, and the project of a
project-level call.

A key that is malformed or resolves to nothing is reported the same way,
"not found: <key>". A project is found by explicit alias, then by the
client's roots, then by the server's working directory; failing all three,
the error lists the known aliases.
"""

import os
import sqlite3

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import TypeAdapter, ValidationError

from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import AbsolutePath, Slug
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.repositories.project import project_alias_db, project_db, project_path_db
from xoot.repositories.session import session_db
from xoot.server.errors import not_found_message
from xoot.server.keys import DECISION_KEY, ITEM_KEY, SESSION_KEY, parse_key
from xoot.server.schemas.literals import ResolvedBy
from xoot.services.lookups import require_project
from xoot.services.project_resolver import ancestors
from xoot.store.store import Store

_SLUG = TypeAdapter(Slug)
_PATH = TypeAdapter(AbsolutePath)


def item_by_key(conn: sqlite3.Connection, key: str) -> Item:
    """
    Fetch an item by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - item (Item): the item.

    Raises:
        - ToolError: the key is malformed or names no item.
    """
    item = None if parse_key(ITEM_KEY, key) is None else item_db.get_by_key(conn, key)
    if item is None:
        raise ToolError(not_found_message(key))
    return item


def optional_item_id(conn: sqlite3.Connection, key: str | None) -> int | None:
    """
    Resolve an optional item key to its id.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str | None): the key, or None.

    Returns:
        - item_id (int | None): the id, or None for None.

    Raises:
        - ToolError: the key is malformed or names no item.
    """
    return None if key is None else item_by_key(conn, key).id


def decision_by_key(conn: sqlite3.Connection, key: str) -> Decision:
    """
    Fetch a decision by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - key (str): the key as the caller sent it.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - ToolError: the key is malformed or names no decision.
    """
    decision = (
        None
        if parse_key(DECISION_KEY, key) is None
        else decision_db.get_by_key(conn, key)
    )
    if decision is None:
        raise ToolError(not_found_message(key))
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
        - ToolError: the key is malformed or names no session.
    """
    parts = parse_key(SESSION_KEY, key)
    project = None if parts is None else project_db.get_by_prefix(conn, parts[0])
    session = (
        None
        if parts is None or project is None
        else session_db.get_by_number(conn, project.id, parts[1])
    )
    if session is None:
        raise ToolError(not_found_message(key))
    return session


def session_writer(store: Store, key: str) -> tuple[Session, WriteContext]:
    """
    Resolve a write tool's session and the context its writes carry.

    The actor is always Claude; the client is the one recorded when the
    session started, so every write of a session is attributed alike.

    Args:
        - store (Store): the database.
        - key (str): the session key.

    Returns:
        - resolved (tuple[Session, WriteContext]): the session and context.

    Raises:
        - ToolError: the key is malformed or names no session.
    """
    with store.read() as conn:
        session = session_by_key(conn, key)
    actor = Actor(kind=ActorKind.CLAUDE, client=session.client)
    return session, WriteContext(actor=actor, session_id=session.id)


def resolve_project(
    store: Store, alias: str | None, root_paths: list[str]
) -> tuple[Project, ResolvedBy]:
    """
    Find the project of a project-level call.

    Args:
        - store (Store): the database.
        - alias (str | None): an explicit alias; roots and cwd are not
          consulted when it is given.
        - root_paths (list[str]): the client's roots as absolute paths.

    Returns:
        - resolved (tuple[Project, ResolvedBy]): the project and the step
          that found it.

    Raises:
        - ToolError: nothing matched; the message lists the known aliases.
    """
    with store.read() as conn:
        if alias is not None:
            project_id = _by_alias(conn, alias)
            if project_id is not None:
                return require_project(conn, project_id), "alias"
            raise ToolError(_unresolved(conn))
        steps: list[tuple[list[str], ResolvedBy]] = [
            (root_paths, "roots"),
            (_cwd(), "cwd"),
        ]
        for paths, resolved_by in steps:
            candidates = sorted({c for path in paths for c in ancestors(path)})
            match = project_path_db.longest_of(conn, candidates)
            if match is not None:
                return require_project(conn, match.project_id), resolved_by
        raise ToolError(_unresolved(conn))


def _by_alias(conn: sqlite3.Connection, alias: str) -> int | None:
    try:
        name = _SLUG.validate_python(alias)
    except ValidationError:
        return None
    match = project_alias_db.get(conn, name)
    return None if match is None else match.project_id


def _cwd() -> list[str]:
    try:
        return [_PATH.validate_python(os.getcwd())]
    except (OSError, ValidationError):
        return []


def _unresolved(conn: sqlite3.Connection) -> str:
    aliases = [entry.alias for entry in project_alias_db.list_all(conn)]
    if not aliases:
        return "project not resolved and no aliases are registered"
    return f"project not resolved; pass project=<alias>, one of: {', '.join(aliases)}"
