"""
Item rules shared by every item write: the hierarchy, workflow states and
same-project references.
"""

import sqlite3

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.state_error import StateError
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.services.lookups import require_decision, require_item, require_session

# The only parent kind each kind may have; None means "no parent allowed".
_PARENT_KIND: dict[ItemKind, ItemKind | None] = {
    ItemKind.GOAL: None,
    ItemKind.BATCH: ItemKind.GOAL,
    ItemKind.SUBTASK: ItemKind.BATCH,
}


def check_parent(
    conn: sqlite3.Connection, project_id: int, kind: ItemKind, parent_id: int | None
) -> None:
    """
    Enforce the hierarchy: goals have no parent, a batch sits under a goal,
    a subtask sits under a batch or nowhere (unfiled).

    The layering also rules out cycles: nothing can sit under a subtask.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the child's project.
        - kind (ItemKind): the child's kind.
        - parent_id (int | None): the proposed parent.

    Raises:
        - HierarchyError: the parent is missing, forbidden or of the wrong kind.
        - NotFoundError: the parent does not exist.
        - CrossProjectError: the parent is in another project.
    """
    allowed = _PARENT_KIND[kind]
    if parent_id is None:
        if kind is ItemKind.BATCH:
            raise HierarchyError("a batch needs a parent goal")
        return
    if allowed is None:
        raise HierarchyError("a goal cannot have a parent")
    parent = require_item(conn, parent_id, project_id)
    if parent.kind is not allowed:
        raise HierarchyError(
            f"a {kind}'s parent must be a {allowed}, not a {parent.kind}"
        )


def check_state(
    workflow: KindWorkflow, state: str, backlog_session_id: int | None
) -> Category:
    """
    Validate a state against the active workflow for the item's kind.

    Args:
        - workflow (KindWorkflow): the kind's active workflow.
        - state (str): the state to validate.
        - backlog_session_id (int | None): the item's session backlog, if any.

    Returns:
        - category (Category): the state's category.

    Raises:
        - StateError: unknown state, or a session backlog outside the
          backlogged category.
    """
    category = workflow.category_of(state)
    if category is None:
        raise StateError(f"state {state!r} is not in the active workflow")
    if backlog_session_id is not None and category is not Category.BACKLOGGED:
        raise StateError("backlog_session_id is only allowed in a backlogged state")
    return category


def check_transition(workflow: KindWorkflow, source: str, target: str) -> None:
    """
    Enforce the workflow's allowed transitions for a user-requested move.

    Args:
        - workflow (KindWorkflow): the kind's active workflow.
        - source (str): current state.
        - target (str): requested state.

    Raises:
        - StateError: the transition is not allowed.
    """
    if not workflow.allows(source, target):
        raise StateError(f"transition {source!r} -> {target!r} is not allowed")


def check_references(
    conn: sqlite3.Connection,
    project_id: int,
    backlog_session_id: int | None,
    awaiting_decision_id: int | None,
) -> None:
    """
    Check an item's session-backlog and awaited-decision references.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the item's project.
        - backlog_session_id (int | None): referenced session.
        - awaiting_decision_id (int | None): referenced decision.

    Raises:
        - NotFoundError: a referenced row does not exist.
        - CrossProjectError: a referenced row is in another project.
    """
    if backlog_session_id is not None:
        require_session(conn, backlog_session_id, project_id)
    if awaiting_decision_id is not None:
        require_decision(conn, awaiting_decision_id, project_id)
