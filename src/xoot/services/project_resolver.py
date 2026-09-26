"""
Finding the project for a working directory or an alias.

Path resolution picks the longest registered path that is the directory
itself or one of its ancestors, compared on whole path segments.
"""

import posixpath

from pydantic import TypeAdapter

from xoot.models.fields import AbsolutePath, Slug
from xoot.models.project.project import Project
from xoot.repositories.project import project_alias_db, project_path_db
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
        match = project_path_db.longest_of(conn, candidates)
        return None if match is None else require_project(conn, match.project_id)


def resolve_by_alias(store: Store, alias: str) -> Project | None:
    """
    Resolve an alias to its project by exact match.

    Args:
        - store (Store): the database.
        - alias (str): the alias.

    Returns:
        - project (Project | None): the project, or None.

    Raises:
        - pydantic.ValidationError: the alias is not a valid slug.
    """
    alias = _SLUG.validate_python(alias)
    with store.read() as conn:
        match = project_alias_db.get(conn, alias)
        return None if match is None else require_project(conn, match.project_id)


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
