"""
Closing a session, as a pure preview plus an apply.

Every linked item that is not done or dropped needs a disposition. Closing
also retires stale session backlogs: items still parked in the backlog of a
session that closed before this one started move to the project backlog.
"Before" is decided by the project's sequence counter, never by the clock,
and those moves are recorded as the system's, not the closer's.

Parent and child states stay independent: the preview only warns when a
disposition leaves an item live under a backlogged or dropped parent.
"""

import sqlite3
from typing import Any

from xoot.exceptions.disposition_error import DispositionError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.event.event_action import EventAction
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.item_kind import ItemKind
from xoot.models.session.close_warning import CloseWarning
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_close_plan import SessionClosePlan
from xoot.models.session.session_status import SessionStatus
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.session import session_db, session_item_ref_db
from xoot.services.confirm_service import check_plan, consume_token, plan_digest
from xoot.services.id_checks import check_id
from xoot.services.item_writer import apply_changes, plan_change
from xoot.services.lookups import (
    active_workflow,
    require_item,
    require_project,
    require_session,
)
from xoot.services.plan_entries import item_entry
from xoot.services.session_links import scope_session_id
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def preview_close(
    store: Store, session_id: int, request: SessionClose
) -> SessionClosePlan:
    """
    Plan closing a session; writes nothing.

    Missing dispositions are reported in the plan rather than raised, so a
    caller can ask for exactly the ones still needed.

    Args:
        - store (Store): the database.
        - session_id (int): session id.
        - request (SessionClose): summary and dispositions so far.

    Returns:
        - plan (SessionClosePlan): what closing would change.

    Raises:
        - InvalidIdError: session_id is not an int id.
        - SessionStateError: the session is already closed.
        - DispositionError: a disposition names an item that needs none.
        - NotFoundError: no such session.
    """
    check_id("session_id", session_id)
    with store.read() as conn:
        return _plan(conn, require_session(conn, session_id), request)


def close_session(
    store: Store,
    session_id: int,
    request: SessionClose,
    actor: Actor,
    confirm: Confirmation | None = None,
) -> Session:
    """
    Close a session: apply dispositions, retire stale backlogs, record all.

    Args:
        - store (Store): the database.
        - session_id (int): session id.
        - request (SessionClose): summary and one disposition per open
          linked item.
        - actor (Actor): who closes it.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.

    Returns:
        - session (Session): the closed session.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - InvalidIdError: session_id is not an int id.
        - DispositionError: a disposition is missing or names an item that
          needs none.
        - SessionStateError: the session is already closed.
        - NotFoundError: no such session.
    """
    check_id("session_id", session_id)
    with store.write() as conn:
        scope = WriteScope(conn, WriteContext(actor=actor, session_id=session_id))
        return close_session_in(scope, request, confirm)


def close_session_in(
    scope: WriteScope, request: SessionClose, confirm: Confirmation | None = None
) -> Session:
    """
    Close the scope's session; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope, attributed to the
          session being closed.
        - request (SessionClose): summary and one disposition per open
          linked item.
        - confirm (Confirmation | None): a token from the preview, consumed
          in the caller's transaction when given.

    Returns:
        - session (Session): the closed session.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - DispositionError: a disposition is missing or names an item that
          needs none.
        - SessionStateError: the scope has no session, or it is already
          closed.
        - NotFoundError: no such session.
    """
    conn = scope.conn
    session_id = scope_session_id(scope)
    token = None if confirm is None else consume_token(conn, confirm, session_id)
    session = require_session(conn, session_id)
    plan = _plan(conn, session, request)
    if plan.missing_item_ids:
        raise DispositionError("missing dispositions for items", plan.missing_item_ids)
    check_plan(token, plan.plan_sha256)
    for item_id, disposition in sorted(plan.dispositions.items()):
        session_item_ref_db.set_disposition(conn, session_id, item_id, disposition)
        scope.noted(
            session,
            EventAction.DISPOSE,
            {"item_id": item_id, "disposition": disposition.value},
            {"item_id": item_id, "disposition": None},
        )
    apply_changes(scope, plan.changes)
    apply_changes(scope.as_system(), plan.auto_backlog)
    closed = session.model_copy(
        update={
            "status": SessionStatus.CLOSED,
            "summary": request.summary,
            "close_seq": project_db.allocate_seq(conn, session.project_id),
            "closed_at": scope.now,
        }
    )
    session_db.update(conn, closed)
    scope.updated(session, closed, EventAction.CLOSE)
    return closed


def _plan(
    conn: sqlite3.Connection, session: Session, request: SessionClose
) -> SessionClosePlan:
    """Compute the close from current rows; shared by preview and apply."""
    if session.status is not SessionStatus.OPEN:
        raise SessionStateError(f"session {session.id} is already closed")
    definition = active_workflow(
        conn, require_project(conn, session.project_id)
    ).definition
    refs = session_item_ref_db.list_for_session(conn, session.id)
    required = [
        item
        for item in (require_item(conn, ref.item_id) for ref in refs)
        if _category(definition, item.kind, item.state) not in TERMINAL_CATEGORIES
    ]
    required_ids = {item.id for item in required}
    unexpected = tuple(sorted(set(request.dispositions) - required_ids))
    if unexpected:
        raise DispositionError(
            "dispositions given for items that need none", unexpected
        )
    changes: list[ItemChange] = []
    rehomed: set[int] = set()
    for item in required:
        disposition = request.dispositions.get(item.id)
        if disposition is None:
            continue
        if disposition is not Disposition.CARRY_OVER:
            rehomed.add(item.id)
        fields = _disposition_fields(
            definition.for_kind(item.kind), disposition, session.id
        )
        change = plan_change(item, fields)
        if change is not None:
            changes.append(change)
    auto_backlog = _stale_backlog(conn, definition, session, rehomed)
    return SessionClosePlan(
        session_id=session.id,
        required_item_ids=tuple(sorted(required_ids)),
        missing_item_ids=tuple(sorted(required_ids - set(request.dispositions))),
        dispositions=dict(request.dispositions),
        changes=tuple(changes),
        auto_backlog=auto_backlog,
        plan_sha256=_digest(
            conn, required, changes, auto_backlog, request.dispositions
        ),
        warnings=_warnings(conn, definition, required, request, changes),
    )


def _digest(
    conn: sqlite3.Connection,
    required: list[Item],
    changes: list[ItemChange],
    auto_backlog: tuple[ItemChange, ...],
    dispositions: dict[int, Disposition],
) -> str:
    """Every required and auto-backlogged item as the close leaves it."""
    fields: dict[int, dict[str, Any]] = {item.id: {} for item in required}
    # Same order as the apply: dispositions first, then the system's moves.
    for change in (*changes, *auto_backlog):
        fields.setdefault(change.item_id, {}).update(change.after)
    return plan_digest(
        item_entry(conn, require_item(conn, item_id), after, dispositions.get(item_id))
        for item_id, after in fields.items()
    )


def _warnings(
    conn: sqlite3.Connection,
    definition: WorkflowDefinition,
    required: list[Item],
    request: SessionClose,
    changes: list[ItemChange],
) -> tuple[CloseWarning, ...]:
    """Flag disposed items left live under a backlogged or dropped parent."""
    closing = {c.item_id: c.after["state"] for c in changes if "state" in c.after}
    warnings = []
    for item in required:
        if item.id not in request.dispositions or item.parent_id is None:
            continue
        parent = require_item(conn, item.parent_id)
        child = _category(definition, item.kind, closing.get(item.id, item.state))
        above = _category(definition, parent.kind, closing.get(parent.id, parent.state))
        if above is not None and _left_under(child, above):
            warnings.append(
                CloseWarning(
                    item_id=item.id,
                    key=item.key,
                    parent_id=parent.id,
                    parent_key=parent.key,
                    parent_category=above,
                )
            )
    return tuple(warnings)


def _left_under(child: Category | None, parent: Category) -> bool:
    """A live child under a dropped parent, or under a backlogged one unless also backlogged."""
    if child in TERMINAL_CATEGORIES:
        return False
    if parent is Category.DROPPED:
        return True
    return parent is Category.BACKLOGGED and child is not Category.BACKLOGGED


def _disposition_fields(
    workflow: KindWorkflow, disposition: Disposition, session_id: int
) -> dict[str, Any]:
    if disposition is Disposition.CARRY_OVER:
        return {}
    if disposition is Disposition.DROPPED:
        return {
            "state": workflow.default_state(Category.DROPPED),
            "backlog_session_id": None,
        }
    backlog = session_id if disposition is Disposition.SESSION_BACKLOG else None
    return {
        "state": workflow.default_state(Category.BACKLOGGED),
        "backlog_session_id": backlog,
    }


def _stale_backlog(
    conn: sqlite3.Connection,
    definition: WorkflowDefinition,
    session: Session,
    rehomed: set[int],
) -> tuple[ItemChange, ...]:
    """Items parked by sessions closed before this one started go to the project backlog."""
    changes = []
    for item in item_db.list_session_backlogged(
        conn, session.project_id, session.start_seq
    ):
        if item.id in rehomed:
            continue
        if _category(definition, item.kind, item.state) is not Category.BACKLOGGED:
            continue
        change = plan_change(item, {"backlog_session_id": None})
        if change is not None:
            changes.append(change)
    return tuple(changes)


def _category(
    definition: WorkflowDefinition, kind: ItemKind, state: str
) -> Category | None:
    return definition.for_kind(kind).category_of(state)
