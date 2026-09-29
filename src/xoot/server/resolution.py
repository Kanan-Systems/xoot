"""
Resolving what a tool call names: its project, and keys to rows.

The project comes from, in order: the explicit project argument, the
"<prefix>:" qualifier of the call's keys, the client's roots, then the
server's working directory; failing all of them, the error lists the known
prefixes and aliases. Keys are then resolved unqualified within it by the
services' key_resolver, whose NotFoundError becomes a ToolError: "not found:
<key>" for a well-formed key, "not found: malformed key" otherwise, since
echoing arbitrary input is unsafe.
"""

import os
import sqlite3
from collections.abc import Callable, Iterable

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import TypeAdapter, ValidationError

from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.qualifier_error import QualifierError
from xoot.models.decision.decision import Decision
from xoot.models.fields import AbsolutePath
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.server.errors import not_found_message, safe_message
from xoot.server.schemas.literals import ResolvedBy
from xoot.services import key_resolver
from xoot.services.project_resolver import (
    ancestors,
    by_named_or_qualified,
    by_paths,
    known_names,
)
from xoot.services.project_scope import key_qualifier, unqualified
from xoot.store.store import Store

_PATH = TypeAdapter(AbsolutePath)


def resolve_project(
    store: Store,
    alias: str | None,
    root_paths: list[str],
    keys: Iterable[str | None] = (),
) -> tuple[Project, ResolvedBy]:
    """
    Find the project of a call.

    Args:
        - store (Store): the database.
        - alias (str | None): the explicit alias or key prefix.
        - root_paths (list[str]): the client's roots as absolute paths.
        - keys (Iterable[str | None]): every key argument of the call, for
          their qualifier.

    Returns:
        - resolved (tuple[Project, ResolvedBy]): the project and the step
          that found it.

    Raises:
        - ToolError: the qualifiers disagree, or nothing matched; the
          message lists the known prefixes and aliases.
    """
    try:
        qualifier = key_qualifier(keys)
    except QualifierError as exc:
        raise ToolError(safe_message(exc)) from exc
    with store.read() as conn:
        try:
            found = by_named_or_qualified(conn, alias, qualifier)
        except QualifierError as exc:
            raise ToolError(safe_message(exc)) from exc
        if found is not None:
            return found
        if alias is not None or qualifier is not None:
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


def item_by_key(conn: sqlite3.Connection, project: Project, key: str) -> Item:
    """
    Fetch an item of the call's project by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project (Project): the call's project.
        - key (str): the key as the caller sent it, qualified or not.

    Returns:
        - item (Item): the item.

    Raises:
        - ToolError: the key is malformed or names no item.
    """
    return _as_tool_error(key_resolver.item_by_key, conn, project, key)


def optional_item_id(
    conn: sqlite3.Connection, project: Project, key: str | None
) -> int | None:
    """
    Resolve an optional item key to its id.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project (Project): the call's project.
        - key (str | None): the key, or None.

    Returns:
        - item_id (int | None): the id, or None for None.

    Raises:
        - ToolError: the key is malformed or names no item.
    """
    return None if key is None else item_by_key(conn, project, key).id


def decision_by_key(conn: sqlite3.Connection, project: Project, key: str) -> Decision:
    """
    Fetch a decision of the call's project by key.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project (Project): the call's project.
        - key (str): the key as the caller sent it, qualified or not.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - ToolError: the key is malformed or names no decision.
    """
    return _as_tool_error(key_resolver.decision_by_key, conn, project, key)


def _as_tool_error[T](
    lookup: Callable[[sqlite3.Connection, int, str], T],
    conn: sqlite3.Connection,
    project: Project,
    key: str,
) -> T:
    try:
        return lookup(conn, project.id, unqualified(key))
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
