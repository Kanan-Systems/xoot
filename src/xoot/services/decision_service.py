"""
Recording and updating decisions.

A decision belongs to the goal, batch or subtask it was made on, which
numbers it. Superseding is part of recording: the newer decision and the
older one's status change commit together, only within one goal, and a
decision is superseded at most once.
"""

import sqlite3
from typing import Any

from xoot.exceptions.decision_error import DecisionError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.decision.new_decision import NewDecision
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import WORK_KINDS, ItemKind
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_decision, require_item, require_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def create_decision(
    store: Store, project_id: int, request: DecisionCreate, ctx: WriteContext
) -> Decision:
    """
    Record a decision, superseding an older one if requested.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - request (DecisionCreate): validated decision details.
        - ctx (WriteContext): the actor.

    Returns:
        - decision (Decision): the new decision.

    Raises:
        - DecisionError: the owner is not a goal, batch or subtask, or the
          superseded decision is already superseded or on another goal.
        - CrossProjectError: a reference is in another project.
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or a reference does not exist.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        return create_decision_in(WriteScope(conn, ctx), project_id, request)


def create_decision_in(
    scope: WriteScope, project_id: int, request: DecisionCreate
) -> Decision:
    """
    Record a decision; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - project_id (int): project id.
        - request (DecisionCreate): validated decision details.

    Returns:
        - decision (Decision): the new decision.

    Raises:
        - DecisionError: the owner is not a goal, batch or subtask, or the
          superseded decision is already superseded or on another goal.
        - CrossProjectError: a reference is in another project.
        - NotFoundError: the project or a reference does not exist.
    """
    conn = scope.conn
    require_project(conn, project_id)
    owner = require_item(conn, request.owner_item_id, project_id)
    if owner.kind not in WORK_KINDS:
        raise DecisionError(
            f"{owner.key} is a backlog item; decisions belong to a goal, batch "
            "or subtask"
        )
    target = None
    if request.supersedes_id is not None:
        target = require_decision(conn, request.supersedes_id, project_id)
        _check_supersede(conn, owner, target)
    number = item_db.allocate(conn, owner.id, "next_decision_number")
    decision = decision_db.insert(
        conn,
        NewDecision(
            project_id=project_id,
            owner_item_id=owner.id,
            number=number,
            title=request.title,
            body=request.body,
            status=request.status,
            supersedes_id=request.supersedes_id,
            created_at=scope.now,
        ),
    )
    scope.created(decision)
    if target is not None:
        _write(scope, target, {"status": DecisionStatus.SUPERSEDED})
    return decision


def update_decision(
    store: Store,
    decision_id: int,
    expected_version: int,
    changes: DecisionUpdate,
    ctx: WriteContext,
) -> Decision:
    """
    Change a decision's title, body or status.

    Args:
        - store (Store): the database.
        - decision_id (int): decision id.
        - expected_version (int): the version the caller read.
        - changes (DecisionUpdate): the fields to change.
        - ctx (WriteContext): the actor.

    Returns:
        - decision (Decision): the stored decision.

    Raises:
        - VersionConflictError: the decision changed since expected_version.
        - DecisionError: the status of a superseded decision cannot change.
        - InvalidIdError: decision_id or expected_version is not an int.
        - NotFoundError: no such decision.
    """
    check_id("decision_id", decision_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        return update_decision_in(
            WriteScope(conn, ctx), decision_id, expected_version, changes
        )


def update_decision_in(
    scope: WriteScope,
    decision_id: int,
    expected_version: int,
    changes: DecisionUpdate,
) -> Decision:
    """
    Change a decision's title, body or status; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - decision_id (int): decision id.
        - expected_version (int): the version the caller read.
        - changes (DecisionUpdate): the fields to change.

    Returns:
        - decision (Decision): the stored decision.

    Raises:
        - VersionConflictError: the decision changed since expected_version.
        - DecisionError: the status of a superseded decision cannot change.
        - NotFoundError: no such decision.
    """
    conn = scope.conn
    decision = require_decision(conn, decision_id)
    ensure_version(conn, EntityType.DECISION, decision, expected_version)
    fields = changes.provided()
    if "status" in fields and decision.status is DecisionStatus.SUPERSEDED:
        raise DecisionError(f"{decision.key} is superseded; record a new decision")
    return _write(scope, decision, fields)


def get_decision(store: Store, decision_id: int) -> Decision:
    """
    Fetch a decision.

    Args:
        - store (Store): the database.
        - decision_id (int): decision id.

    Returns:
        - decision (Decision): the decision.

    Raises:
        - InvalidIdError: decision_id is not an int id.
        - NotFoundError: no such decision.
    """
    check_id("decision_id", decision_id)
    with store.read() as conn:
        return require_decision(conn, decision_id)


def goal_of(conn: sqlite3.Connection, item: Item) -> Item:
    """
    Return the goal an item belongs to.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item (Item): a goal, batch or subtask.

    Returns:
        - goal (Item): the item itself for a goal, else its goal.
    """
    current = item
    while current.kind is not ItemKind.GOAL and current.parent_id is not None:
        current = require_item(conn, current.parent_id)
    return current


def _check_supersede(conn: sqlite3.Connection, owner: Item, target: Decision) -> None:
    """A decision supersedes one of the same goal, and only one never superseded."""
    if target.status is DecisionStatus.SUPERSEDED:
        raise DecisionError(f"{target.key} is already superseded")
    target_owner = require_item(conn, target.owner_item_id)
    if goal_of(conn, target_owner).id != goal_of(conn, owner).id:
        raise DecisionError(
            f"{target.key} is on another goal; a decision supersedes only "
            "decisions of its own goal"
        )


def _write(scope: WriteScope, decision: Decision, fields: dict[str, Any]) -> Decision:
    """Validate, bump the version, store and record one decision change."""
    candidate = Decision.model_validate({**decision.model_dump(), **fields})
    if candidate == decision:
        return decision
    stored = candidate.model_copy(
        update={"version": decision.version + 1, "updated_at": scope.now}
    )
    decision_db.update(scope.conn, stored, decision.version)
    scope.updated(decision, stored)
    return stored
