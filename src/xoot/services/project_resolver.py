"""
Finding the project for a working directory, an alias or a key prefix.

Prefixes and aliases share one namespace, so a name resolves to at most one
project. Path resolution picks the longest registered path that is the
directory itself or one of its ancestors, compared on whole path segments.
"""

import posixpath
import sqlite3

from pydantic import TypeAdapter, ValidationError

from xoot.exceptions.project_resolution_error import ProjectResolutionError
from xoot.models.fields import AbsolutePath, Slug
from xoot.models.project.project import Project
from xoot.repositories.project import project_alias_db, project_db, project_path_db
from xoot.services.lookups import require_project
from xoot.store.store import Store

_SLUG = TypeAdapter(Slug)
_PATH = TypeAdapter(AbsolutePath)


def resolve_by_path(store: Store, path: str) -> Project | None:
    """
    Resolve a directory to its project by longest whole-segment match.

    Args:
        - store (Store): the database.
        - path (str): an absolute directory path.

    Returns:
        - project (Project | None): the owning project, or None.

    Raises:
        - pydantic.ValidationError: the path is not absolute or too long.
    """
    candidates = ancestors(_PATH.validate_python(path))
    with store.read() as conn:
        return by_paths(conn, candidates)


def resolve_by_alias(store: Store, alias: str) -> Project | None:
    """
    Resolve an alias or a key prefix to its project by exact match.

    Args:
        - store (Store): the database.
        - alias (str): the alias or prefix.

    Returns:
        - project (Project | None): the project, or None.

    Raises:
        - pydantic.ValidationError: the name is not a valid slug.
    """
    alias = _SLUG.validate_python(alias)
    with store.read() as conn:
        return by_name(conn, alias)


def resolve_project(store: Store, name: str | None, cwd: str) -> Project:
    """
    Find a project by name, or else by the directory a command runs in.

    Args:
        - store (Store): the database.
        - name (str | None): an alias or prefix; the directory is not
          consulted when it is given.
        - cwd (str): an absolute directory.

    Returns:
        - project (Project): the project.

    Raises:
        - ProjectResolutionError: nothing matched; lists every known name.
    """
    with store.read() as conn:
        if name is not None:
            found = by_name(conn, name)
        else:
            try:
                found = by_paths(conn, ancestors(_PATH.validate_python(cwd)))
            except ValidationError:
                found = None
        if found is None:
            raise ProjectResolutionError(tuple(known_names(conn)))
        return found


def by_name(conn: sqlite3.Connection, name: str) -> Project | None:
    """
    Look a project up by alias, then by key prefix.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - name (str): caller input; anything that is not a slug matches
          nothing.

    Returns:
        - project (Project | None): the project, or None.
    """
    try:
        slug = _SLUG.validate_python(name)
    except ValidationError:
        return None
    alias = project_alias_db.get(conn, slug)
    if alias is not None:
        return require_project(conn, alias.project_id)
    return project_db.get_by_prefix(conn, slug)


def by_paths(conn: sqlite3.Connection, candidates: list[str]) -> Project | None:
    """
    Look a project up by the longest registered path among candidates.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - candidates (list[str]): normalized whole-segment paths.

    Returns:
        - project (Project | None): the owning project, or None.
    """
    match = project_path_db.longest_of(conn, candidates)
    return None if match is None else require_project(conn, match.project_id)


def known_names(conn: sqlite3.Connection) -> list[str]:
    """
    List every key prefix and alias, sorted and without repeats.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.

    Returns:
        - names (list[str]): every name that resolves to a project.
    """
    prefixes = {project.key_prefix for project in project_db.list_all(conn)}
    aliases = {entry.alias for entry in project_alias_db.list_all(conn)}
    return sorted(prefixes | aliases)


def ancestors(path: str) -> list[str]:
    """
    List a normalized path and each ancestor directory, longest first.

    Building whole-segment candidates is what keeps /a/xoot from matching
    /a/xoot2: a prefix that is not a full segment never appears.

    Args:
        - path (str): an absolute, normalized path.

    Returns:
        - paths (list[str]): e.g. ["/a/b", "/a", "/"] for "/a/b".
    """
    result = [path]
    while path != "/":
        path = posixpath.dirname(path)
        result.append(path)
    return result
