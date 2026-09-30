"""Project-level responses: projects, brief, tree, backlog, decisions, changes."""

import sqlite3

from xoot.dashboard.params.tree_params import TreeParams
from xoot.dashboard.schemas.backlog_row import BacklogRow
from xoot.dashboard.schemas.backlog_view import BacklogView
from xoot.dashboard.schemas.brief_view import BriefView
from xoot.dashboard.schemas.changes_view import ChangesView
from xoot.dashboard.schemas.decisions_view import DecisionsView
from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.dashboard.schemas.projects_output import ProjectsOutput
from xoot.dashboard.schemas.tree_view import TreeView
from xoot.dashboard.schemas.workflow_kind_view import WorkflowKindView
from xoot.dashboard.schemas.workflow_view import WorkflowView
from xoot.dashboard.views.lookup import item_of, project_of
from xoot.models.fields import format_timestamp
from xoot.models.item.tree_query import TreeQuery
from xoot.models.project.project_overview import ProjectOverview
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.repositories.decision import decision_db
from xoot.repositories.project import project_db
from xoot.server.brief import build_brief
from xoot.server.key_book import KeyBook
from xoot.server.render import decision_summary, item_summary, tree_entries
from xoot.server.schemas.blocked_entry import BlockedEntry
from xoot.services.backlog_reads import backlog_items, backlog_level, blocked_items
from xoot.services.history_service import latest_event_id
from xoot.services.lookups import active_workflow
from xoot.services.project_service import overview
from xoot.services.tree_service import tree_in

# Fields of brief_get that only make sense to an MCP client (kanan-66).
_MCP_ONLY = {"header", "resolved_by", "db_path", "project"}
BACKLOG_MAX = 200
# High enough that the tree's decision badges count every decision of a
# typical project; truncated says when they may not.
DECISIONS_MAX = 500
# The backlog table shows one line of why; the drawer has the full body.
WHY_MAX = 200


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
        - output (ProjectsOutput): the projects, by prefix.
    """
    return ProjectsOutput(
        projects=[project_info(overview(conn, p)) for p in project_db.list_all(conn)]
    )


def brief_view(conn: sqlite3.Connection, prefix: str) -> BriefView:
    """
    Build a project's brief without the MCP-only fields.

    build_brief is reused so both views stay identical; no database path is
    passed, so none can reach the browser.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (BriefView): the brief.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    brief = build_brief(conn, project, "prefix")
    return BriefView(
        **brief.model_dump(exclude=_MCP_ONLY),
        project=project_info(overview(conn, project)),
    )


def tree_view(conn: sqlite3.Connection, prefix: str, params: TreeParams) -> TreeView:
    """
    Return a project's tree, or one goal's.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - params (TreeParams): goal key, depth, done filter and limit.

    Returns:
        - view (TreeView): nodes in pre-order, a truncated flag, and every
          goal and batch that open backlog holds open.

    Raises:
        - ApiError: 404, no such project or goal.
    """
    project = project_of(conn, prefix)
    query = TreeQuery(
        root_id=None if params.goal is None else item_of(conn, project, params.goal).id,
        depth=params.depth,
        max_items=params.limit,
        include_terminal=params.include_done,
    )
    result = tree_in(conn, project.id, query)
    return TreeView(
        project=project.key_prefix,
        nodes=tree_entries(KeyBook(conn), result),
        truncated=result.truncated,
        blocked=[
            BlockedEntry(key=b.key, open_backlog=b.open_backlog)
            for b in blocked_items(conn, project.id)
        ],
    )


def backlog_view(conn: sqlite3.Connection, prefix: str) -> BacklogView:
    """
    List a project's open backlog, every level.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (BacklogView): up to BACKLOG_MAX items.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    book = KeyBook(conn)
    items = backlog_items(conn, project.id)
    return BacklogView(
        project=project.key_prefix,
        items=[
            BacklogRow(
                **item_summary(book, item).model_dump(),
                level=backlog_level(item),
                found_on=book.item_key(item.found_on_item_id),
                created_at=format_timestamp(item.created_at),
                why=first_line(item.body),
            )
            for item in items[:BACKLOG_MAX]
        ],
        truncated=len(items) > BACKLOG_MAX,
    )


def decisions_view(conn: sqlite3.Connection, prefix: str) -> DecisionsView:
    """
    List a project's decisions, newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (DecisionsView): up to DECISIONS_MAX decisions.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    book = KeyBook(conn)
    rows = decision_db.list_recent(conn, project.id, None, DECISIONS_MAX + 1)
    return DecisionsView(
        project=project.key_prefix,
        decisions=[decision_summary(book, d) for d in rows[:DECISIONS_MAX]],
        truncated=len(rows) > DECISIONS_MAX,
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


def workflow_view(conn: sqlite3.Connection, prefix: str) -> WorkflowView:
    """
    Report every item kind's states, categories and allowed moves from the
    active workflow.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (WorkflowView): the states per kind.

    Raises:
        - ApiError: 404, no such project.
    """
    definition = active_workflow(conn, project_of(conn, prefix)).definition
    return WorkflowView(
        workflow={kind: _kind_view(flow) for kind, flow in definition.kinds.items()}
    )


def _kind_view(workflow: KindWorkflow) -> WorkflowKindView:
    """
    One kind's states and moves. The moves are read through allows(), the
    rule check_transition applies, so the map can never disagree with it.
    """
    names = [spec.name for spec in workflow.states]
    moves = None
    if workflow.transitions is not None:
        moves = {
            source: [t for t in names if t != source and workflow.allows(source, t)]
            for source in names
        }
    return WorkflowKindView(
        states=list(workflow.states),
        transitions_restricted=workflow.transitions is not None,
        transitions=moves,
    )


def first_line(body: str) -> str:
    """
    Cut a body to its first non-empty line, at most WHY_MAX characters.

    Args:
        - body (str): the stored body.

    Returns:
        - line (str): the line, stripped; empty when the body is blank.
    """
    for line in body.splitlines():
        if line.strip():
            return line.strip()[:WHY_MAX]
    return ""
