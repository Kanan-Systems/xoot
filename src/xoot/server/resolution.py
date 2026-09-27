"""
Resolving what a tool call names: public keys to rows, and the project of a
project-level call.

Key lookups are the services' key_resolver, with its NotFoundError turned
into a ToolError. A well-formed key that resolves to nothing is reported as
"not found: <key>"; a malformed key as "not found: malformed key", since
echoing arbitrary input is unsafe. A project is found by explicit alias or
key prefix, then by the client's roots, then by the server's working
directory; failing all three, the error lists the known prefixes and aliases.
"""

import os
import sqlite3
from collections.abc import Callable

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import TypeAdapter, ValidationError

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import AbsolutePath
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.server.errors import not_found_message
from xoot.server.schemas.literals import ResolvedBy
from xoot.services import key_resolver
from xoot.services.project_resolver import ancestors, by_name, by_paths, known_names
from xoot.store.store import Store

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
    return _as_tool_error(key_resolver.item_by_key, conn, key)


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
    return _as_tool_error(key_resolver.decision_by_key, conn, key)


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
    return _as_tool_error(key_resolver.session_by_key, conn, key)


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
        - alias (str | None): an explicit alias or key prefix; roots and cwd
          are not consulted when it is given.
        - root_paths (list[str]): the client's roots as absolute paths.

    Returns:
        - resolved (tuple[Project, ResolvedBy]): the project and the step
          that found it.

    Raises:
        - ToolError: nothing matched; the message lists the known prefixes
          and aliases.
    """
    with store.read() as conn:
        if alias is not None:
            found = by_name(conn, alias)
            if found is not None:
                return found, "alias"
            raise ToolError(_unresolved(conn))
        steps: list[tuple[list[str], ResolvedBy]] = [
            (root_paths, "roots"),
            (_cwd(), "cwd"),
        ]
        for paths, resolved_by in steps:
            candidates = sorted({c for path in paths for c in ancestors(path)})
            match = by_paths(conn, candidates)
            if match is not None:
                return match, resolved_by
        raise ToolError(_unresolved(conn))


def _as_tool_error[T](
    lookup: Callable[[sqlite3.Connection, str], T], conn: sqlite3.Connection, key: str
) -> T:
    try:
        return lookup(conn, key)
    except NotFoundError as exc:
        raise ToolError(not_found_message(key)) from exc


def _cwd() -> list[str]:
    try:
        return [_PATH.validate_python(os.getcwd())]
    except (OSError, ValidationError):
        return []


def _unresolved(conn: sqlite3.Connection) -> str:
    names = known_names(conn)
    if not names:
        return "project not resolved and no projects are registered"
    return (
        "project not resolved; pass project=<alias or prefix>, "
        f"one of: {', '.join(names)}"
    )
