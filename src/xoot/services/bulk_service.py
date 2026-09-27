"""
Creating a tree of new items in one transaction, as a preview plus an apply.

The preview validates every node in a read-only snapshot and returns the keys
the items would get. The apply consumes its confirm token, re-plans under the
write lock, refuses a plan that differs from the preview's, and inserts every
item, or none of them.
"""

import sqlite3

from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.bulk_plan import BulkPlan
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.planned_item import PlannedItem
from xoot.models.session.session import Session
from xoot.models.session.session_status import SessionStatus
from xoot.models.workflow.category import Category
from xoot.services.confirm_service import check_plan, consume_token, plan_digest
from xoot.services.id_checks import check_id
from xoot.services.item_rules import check_child_kind, check_parent
from xoot.services.item_writer import insert_item
from xoot.services.lookups import (
    active_workflow,
    require_item,
    require_project,
    require_session,
)
from xoot.services.session_links import link_items, scope_session_id
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store
from xoot.utils.utils import body_digest


def preview_bulk(store: Store, session_id: int, request: BulkCreate) -> BulkPlan:
    """
    Validate a bulk create and plan its keys; writes nothing.

    Args:
        - store (Store): the database.
        - session_id (int): the open session the items belong to.
        - request (BulkCreate): the nodes to create.

    Returns:
        - plan (BulkPlan): every planned item, in insert order.

    Raises:
        - InvalidIdError: session_id is not an int id.
        - SessionStateError: the session is closed.
        - HierarchyError: a node's parent kind is not allowed.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the session or an existing parent does not exist.
    """
    check_id("session_id", session_id)
    with store.read() as conn:
        return _plan(conn, _open_session(conn, session_id), request)


def apply_bulk(
    store: Store,
    session_id: int,
    request: BulkCreate,
    actor: Actor,
    confirm: Confirmation | None = None,
) -> tuple[Item, ...]:
    """
    Create every node of a bulk create, all or nothing.

    Args:
        - store (Store): the database.
        - session_id (int): the open session the items belong to (all are
          linked to it).
        - request (BulkCreate): the nodes to create.
        - actor (Actor): who creates them.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.

    Returns:
        - items (tuple[Item, ...]): the stored items, in insert order.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          planned keys changed since the preview.
        - InvalidIdError: session_id is not an int id.
        - SessionStateError: the session is closed.
        - HierarchyError: a node's parent kind is not allowed.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the session or an existing parent does not exist.
    """
    check_id("session_id", session_id)
    with store.write() as conn:
        scope = WriteScope(conn, WriteContext(actor=actor, session_id=session_id))
        return apply_bulk_in(scope, request, confirm)


def apply_bulk_in(
    scope: WriteScope, request: BulkCreate, confirm: Confirmation | None = None
) -> tuple[Item, ...]:
    """
    Create every node of a bulk create; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope, attributed to the open
          session the items belong to (all are linked to it).
        - request (BulkCreate): the nodes to create.
        - confirm (Confirmation | None): a token from the preview, consumed
          in the caller's transaction when given.

    Returns:
        - items (tuple[Item, ...]): the stored items, in insert order.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          planned keys changed since the preview.
        - SessionStateError: the scope has no session, or it is closed.
        - HierarchyError: a node's parent kind is not allowed.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the session or an existing parent does not exist.
    """
    conn = scope.conn
    session_id = scope_session_id(scope)
    token = None if confirm is None else consume_token(conn, confirm, session_id)
    session = _open_session(conn, session_id)
    check_plan(token, _plan(conn, session, request).plan_sha256)
    project = require_project(conn, session.project_id)
    definition = active_workflow(conn, project).definition
    created: list[Item] = []
    for node, parent in request.walk():
        new = ItemCreate(
            kind=node.kind,
            title=node.title,
            body=node.body,
            parent_id=node.parent_id if parent is None else created[parent].id,
            state=definition.for_kind(node.kind).default_state(Category.OPEN),
        )
        created.append(insert_item(scope, project, new))
    link_items(scope, session, [item.id for item in created])
    return tuple(created)


def _open_session(conn: sqlite3.Connection, session_id: int) -> Session:
    session = require_session(conn, session_id)
    if session.status is not SessionStatus.OPEN:
        raise SessionStateError(f"session {session_id} is closed")
    return session


def _plan(conn: sqlite3.Connection, session: Session, request: BulkCreate) -> BulkPlan:
    """Check every node against the current rows and assign planned keys."""
    project = require_project(conn, session.project_id)
    definition = active_workflow(conn, project).definition
    planned: list[PlannedItem] = []
    entries: list[PlanEntry] = []
    for node, parent in request.walk():
        if parent is None:
            check_parent(conn, project.id, node.kind, node.parent_id)
            parent_key = (
                None
                if node.parent_id is None
                else require_item(conn, node.parent_id, project.id).key
            )
        else:
            check_child_kind(planned[parent].kind, node.kind)
            parent_key = planned[parent].key
        number = project.next_item_number + len(planned)
        item = PlannedItem(
            key=f"{project.key_prefix}-{number}",
            kind=node.kind,
            title=node.title,
            parent_key=parent_key,
        )
        planned.append(item)
        # A new item starts with no backlog session and no awaited decision.
        entries.append(
            PlanEntry(
                key=item.key,
                kind=item.kind,
                title=item.title,
                body_sha256=body_digest(node.body),
                state=definition.for_kind(item.kind).default_state(Category.OPEN),
                parent_key=parent_key,
                backlog_session_key=None,
                awaiting_decision_key=None,
            )
        )
    return BulkPlan(
        session_id=session.id, items=tuple(planned), plan_sha256=plan_digest(entries)
    )
