"""
Fetch-or-raise helpers shared by the services.

Repositories return None for a missing row; services turn that into a
NotFoundError, and a row from another project into a CrossProjectError.
"""

import sqlite3

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision import Decision
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.workflow.workflow import Workflow
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.session import session_db
from xoot.repositories.workflow import workflow_db


def require_project(conn: sqlite3.Connection, project_id: int) -> Project:
    """
    Fetch a project or raise.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - project (Project): the project.

    Raises:
        - NotFoundError: no such project.
    """
    project = project_db.get(conn, project_id)
    if project is None:
        raise NotFoundError("project", project_id)
    return project


def require_item(
    conn: sqlite3.Connection, item_id: int, project_id: int | None = None
) -> Item:
    """
    Fetch an item or raise, optionally requiring a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): item id.
        - project_id (int | None): the project the item must belong to.

    Returns:
        - item (Item): the item.

    Raises:
        - NotFoundError: no such item.
        - CrossProjectError: the item is in another project.
    """
    item = item_db.get(conn, item_id)
    if item is None:
        raise NotFoundError("item", item_id)
    _same_project("item", item.key, item.project_id, project_id)
    return item


def require_session(
    conn: sqlite3.Connection, session_id: int, project_id: int | None = None
) -> Session:
    """
    Fetch a session or raise, optionally requiring a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - session_id (int): session id.
        - project_id (int | None): the project the session must belong to.

    Returns:
        - session (Session): the session.

    Raises:
        - NotFoundError: no such session.
        - CrossProjectError: the session is in another project.
    """
    session = session_db.get(conn, session_id)
    if session is None:
        raise NotFoundError("session", session_id)
    _same_project("session", session_id, session.project_id, project_id)
    return session


def require_decision(
    conn: sqlite3.Connection, decision_id: int, project_id: int | None = None
) -> Decision:
    """
    Fetch a decision or raise, optionally requiring a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - decision_id (int): decision id.
        - project_id (int | None): the project the decision must belong to.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - NotFoundError: no such decision.
        - CrossProjectError: the decision is in another project.
    """
    decision = decision_db.get(conn, decision_id)
    if decision is None:
        raise NotFoundError("decision", decision_id)
    _same_project("decision", decision.key, decision.project_id, project_id)
    return decision


def active_workflow(conn: sqlite3.Connection, project: Project) -> Workflow:
    """
    Fetch the workflow version a project currently uses.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project (Project): the project.

    Returns:
        - workflow (Workflow): the active version.

    Raises:
        - NotFoundError: the project has no active workflow (a registration
          that did not complete; never expected after commit).
    """
    workflow = None
    if project.active_workflow_id is not None:
        workflow = workflow_db.get(conn, project.active_workflow_id)
    if workflow is None:
        raise NotFoundError("active workflow of project", project.key_prefix)
    return workflow


def _same_project(entity: str, ref: object, actual: int, expected: int | None) -> None:
    if expected is not None and actual != expected:
        raise CrossProjectError(f"{entity} {ref} belongs to another project")
