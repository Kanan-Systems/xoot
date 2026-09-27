"""
Recording and updating decisions.

Superseding is part of recording: the newer decision and the older one's
status change commit together.
"""

from typing import Any

from xoot.exceptions.decision_error import DecisionError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.decision.new_decision import NewDecision
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.repositories.decision import decision_db
from xoot.repositories.project import project_db
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_decision, require_item, require_project
from xoot.services.session_links import open_session_for
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
        - ctx (WriteContext): actor and optional session.

    Returns:
        - decision (Decision): the new decision.

    Raises:
        - DecisionError: the superseded decision is already superseded.
        - CrossProjectError: a reference is in another project.
        - SessionStateError: the session is closed.
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or a reference does not exist.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        project = require_project(conn, project_id)
        open_session_for(conn, project_id, ctx.session_id)
        target = None
        if request.supersedes_id is not None:
            target = require_decision(conn, request.supersedes_id, project_id)
            if target.status is DecisionStatus.SUPERSEDED:
                raise DecisionError(f"{target.key} is already superseded")
        if request.scope_item_id is not None:
            require_item(conn, request.scope_item_id, project_id)
        scope = WriteScope(conn, ctx)
        number = project_db.allocate_decision_number(conn, project_id)
        decision = decision_db.insert(
            conn,
            NewDecision(
                project_id=project_id,
                number=number,
                key=f"{project.key_prefix}-D{number}",
                title=request.title,
                body=request.body,
                status=request.status,
                supersedes_id=request.supersedes_id,
                scope_item_id=request.scope_item_id,
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
        - ctx (WriteContext): actor and optional session.

    Returns:
        - decision (Decision): the stored decision.

    Raises:
        - VersionConflictError: the decision changed since expected_version.
        - DecisionError: the status of a superseded decision cannot change.
        - SessionStateError: the session is closed.
        - InvalidIdError: decision_id or expected_version is not an int.
        - NotFoundError: no such decision.
    """
    check_id("decision_id", decision_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        decision = require_decision(conn, decision_id)
        ensure_version(conn, EntityType.DECISION, decision, expected_version)
        open_session_for(conn, decision.project_id, ctx.session_id)
        fields = changes.provided()
        if "status" in fields and decision.status is DecisionStatus.SUPERSEDED:
            raise DecisionError(f"{decision.key} is superseded; record a new decision")
        return _write(WriteScope(conn, ctx), decision, fields)


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
