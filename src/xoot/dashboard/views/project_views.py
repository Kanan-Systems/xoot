"""Project-level responses: the project list, brief, tree and change marker."""

import sqlite3
from pathlib import Path

from xoot.dashboard.params.tree_params import TreeParams
from xoot.dashboard.schemas.brief_view import BriefView
from xoot.dashboard.schemas.changes_view import ChangesView
from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.dashboard.schemas.projects_output import ProjectsOutput
from xoot.dashboard.schemas.tree_view import TreeView
from xoot.dashboard.views.lookup import item_of, project_of
from xoot.models.item.tree_query import TreeQuery
from xoot.models.project.project_overview import ProjectOverview
from xoot.repositories.project import project_db
from xoot.server.brief import build_brief
from xoot.server.key_book import KeyBook
from xoot.server.render import tree_entries
from xoot.services.history_service import latest_event_id
from xoot.services.project_service import overview
from xoot.services.tree_service import tree_in

# Fields of brief_get that only make sense to an MCP client (kanan-66).
_MCP_ONLY = {"header", "resolved_by", "db_path", "project"}


def project_info(listed: ProjectOverview) -> ProjectInfo:
    """
    Render a project for the switcher, without its local paths.

    Args:
        - listed (ProjectOverview): the project and its aliases.

    Returns:
        - info (ProjectInfo): prefix, name and aliases.
    """
    return ProjectInfo(
        key_prefix=listed.project.key_prefix,
        name=listed.project.name,
        aliases=list(listed.aliases),
    )


def projects_view(conn: sqlite3.Connection) -> ProjectsOutput:
    """
    List every registered project.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.

    Returns:
        - output (ProjectsOutput): the projects, by id.
    """
    return ProjectsOutput(
        projects=[project_info(overview(conn, p)) for p in project_db.list_all(conn)]
    )


def brief_view(conn: sqlite3.Connection, prefix: str) -> BriefView:
    """
    Build a project's brief without the MCP-only fields.

    build_brief is reused so both views stay identical; the path it is
    handed is dropped with the other MCP-only fields and never sent.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (BriefView): the brief.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    brief = build_brief(conn, project, "prefix", Path())
    return BriefView(
        **brief.model_dump(exclude=_MCP_ONLY),
        project=project_info(overview(conn, project)),
    )


def tree_view(conn: sqlite3.Connection, prefix: str, params: TreeParams) -> TreeView:
    """
    Return part of a project's tree.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - params (TreeParams): root key, depth, done filter and limit.

    Returns:
        - view (TreeView): nodes in pre-order and a truncated flag.

    Raises:
        - ApiError: 404, no such project or root item.
        - CrossProjectError: the root item is in another project.
    """
    project = project_of(conn, prefix)
    query = TreeQuery(
        root_id=None if params.root is None else item_of(conn, params.root).id,
        depth=params.depth,
        max_items=params.limit,
        include_terminal=params.include_done,
    )
    result = tree_in(conn, project.id, query)
    return TreeView(
        project=project.key_prefix,
        nodes=tree_entries(KeyBook(conn), result),
        truncated=result.truncated,
    )


def changes_view(conn: sqlite3.Connection, prefix: str) -> ChangesView:
    """
    Report the project's newest event id, for polling.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (ChangesView): the latest event id.

    Raises:
        - ApiError: 404, no such project.
    """
    return ChangesView(
        latest_event_id=latest_event_id(conn, project_of(conn, prefix).id)
    )
