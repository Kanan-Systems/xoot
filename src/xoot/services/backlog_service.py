"""
Backlog reads: the three backlog scopes and the backlogs of open sessions.

Every function takes a connection inside the caller's read transaction, so
a view built from several of them sees one snapshot. Nothing here imports
the MCP server; the MCP tools, the CLI and the dashboard share these.
"""

import sqlite3

from xoot.models.item.backlog_scope import BacklogScope
from xoot.models.item.item import Item
from xoot.models.session.session_backlog import SessionBacklog
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.repositories.session import session_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import active_workflow, require_project

# Open sessions are few; the cap only bounds a pathological project.
OPEN_SESSIONS_MAX = 1000


def backlog_items(
    conn: sqlite3.Connection, project_id: int, scope: BacklogScope
) -> list[Item]:
    """
    List every item of one backlog scope, by number.

    A captured item sits in both the session and the unfiled scope: it is
    backlogged in a session and has no batch.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.
        - scope (BacklogScope): session, project or unfiled.

    Returns:
        - items (list[Item]): the matching items, uncapped.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or its workflow is missing.
    """
    definition = _definition(conn, project_id)
    return [
        item
        for item in item_db.list_for_project(conn, project_id)
        if _in_scope(scope, item, _category(definition, item))
    ]


def open_session_backlog(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List the items held in the backlogs of the project's open sessions.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.

    Returns:
        - items (list[Item]): by session number, then item number.

    Raises:
        - InvalidIdError: project_id is not an int id.
    """
    check_id("project_id", project_id)
    return item_db.list_open_session_backlogged(conn, project_id)


def session_backlogs(conn: sqlite3.Connection, project_id: int) -> list[SessionBacklog]:
    """
    Group the open-session backlog items by session, one entry per open
    session, empty backlogs included.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.

    Returns:
        - backlogs (list[SessionBacklog]): open sessions, oldest first.

    Raises:
        - InvalidIdError: project_id is not an int id.
    """
    held: dict[int, list[Item]] = {}
    for item in open_session_backlog(conn, project_id):
        if item.backlog_session_id is not None:
            held.setdefault(item.backlog_session_id, []).append(item)
    return [
        SessionBacklog(session=session, items=tuple(held.get(session.id, [])))
        for session in session_db.list_open(conn, project_id, OPEN_SESSIONS_MAX)
    ]


def _definition(conn: sqlite3.Connection, project_id: int) -> WorkflowDefinition:
    check_id("project_id", project_id)
    return active_workflow(conn, require_project(conn, project_id)).definition


def _category(definition: WorkflowDefinition, item: Item) -> Category | None:
    return definition.for_kind(item.kind).category_of(item.state)


def _in_scope(scope: BacklogScope, item: Item, category: Category | None) -> bool:
    if scope == "unfiled":
        return item.unfiled and category not in TERMINAL_CATEGORIES
    if category is not Category.BACKLOGGED:
        return False
    return (item.backlog_session_id is not None) == (scope == "session")
