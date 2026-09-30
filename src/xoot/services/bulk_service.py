"""
Creating a tree of new items in one transaction, as a preview plus an apply.

The preview validates every node in a read-only snapshot and returns the keys
the items would get. The apply consumes its confirm token, re-plans under the
write lock, refuses a plan that differs from the preview's, and inserts every
item, or none of them.
"""

import sqlite3

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.bulk_item import BulkItem
from xoot.models.item.bulk_plan import BulkPlan
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.planned_item import PlannedItem
from xoot.models.workflow.category import Category
from xoot.services.confirm_service import check_plan, consume_token, plan_digest
from xoot.services.id_checks import check_id
from xoot.services.item_rules import check_child_kind, check_parent
from xoot.services.item_service import BACKLOG_VIA_CAPTURE
from xoot.services.item_store import peek_number
from xoot.services.item_writer import insert_item
from xoot.services.lookups import active_workflow, require_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store
from xoot.utils.keys import child_key
from xoot.utils.utils import body_digest


def preview_bulk(store: Store, project_id: int, request: BulkCreate) -> BulkPlan:
    """
    Validate a bulk create and plan its keys; writes nothing.

    Args:
        - store (Store): the database.
        - project_id (int): the project the items belong to.
        - request (BulkCreate): the nodes to create.

    Returns:
        - plan (BulkPlan): every planned item, in insert order.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - HierarchyError: a node's parent kind is not allowed, or a node is
          a backlog item.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the project or an existing parent does not exist.
    """
    check_id("project_id", project_id)
    with store.read() as conn:
        return _plan(conn, project_id, request)


def apply_bulk(
    store: Store,
    project_id: int,
    request: BulkCreate,
    ctx: WriteContext,
    confirm: Confirmation | None = None,
) -> tuple[tuple[Item, ...], CompletionReport]:
    """
    Create every node of a bulk create, all or nothing.

    Args:
        - store (Store): the database.
        - project_id (int): the project the items belong to.
        - request (BulkCreate): the nodes to create.
        - ctx (WriteContext): the actor.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.

    Returns:
        - created (tuple[tuple[Item, ...], CompletionReport]): the stored
          items, in insert order, and what the completion engine did.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          planned keys changed since the preview.
        - InvalidIdError: project_id is not an int id.
        - HierarchyError: a node's parent kind is not allowed.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the project or an existing parent does not exist.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        items = apply_bulk_in(scope, project_id, request, confirm)
        return items, scope.report()


def apply_bulk_in(
    scope: WriteScope,
    project_id: int,
    request: BulkCreate,
    confirm: Confirmation | None = None,
) -> tuple[Item, ...]:
    """
    Create every node of a bulk create; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - project_id (int): the project the items belong to.
        - request (BulkCreate): the nodes to create.
        - confirm (Confirmation | None): a token from the preview, consumed
          in the caller's transaction when given.

    Returns:
        - items (tuple[Item, ...]): the stored items, in insert order.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          planned keys changed since the preview.
        - HierarchyError: a node's parent kind is not allowed.
        - CrossProjectError: an existing parent is in another project.
        - NotFoundError: the project or an existing parent does not exist.
    """
    conn = scope.conn
    token = (
        None
        if confirm is None
        else consume_token(conn, confirm, project_id, scope.ctx.actor)
    )
    check_plan(token, _plan(conn, project_id, request).plan_sha256)
    project = require_project(conn, project_id)
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
    return tuple(created)


def _plan(conn: sqlite3.Connection, project_id: int, request: BulkCreate) -> BulkPlan:
    """Check every node against the current rows and assign planned keys."""
    project = require_project(conn, project_id)
    definition = active_workflow(conn, project).definition
    planned: list[PlannedItem] = []
    entries: list[PlanEntry] = []
    # Numbers already planned per (existing or planned parent, counter).
    taken: dict[tuple[str, str | None], int] = {}
    for node, parent in request.walk():
        parent_key, first = _parent_slot(conn, project.id, node, planned, parent)
        slot = (node.kind.value, parent_key)
        number = taken.get(slot, first)
        taken[slot] = number + 1
        item = PlannedItem(
            key=child_key(parent_key, node.kind, number),
            kind=node.kind,
            title=node.title,
            parent_key=parent_key,
        )
        planned.append(item)
        # A new item starts with no awaited decision.
        entries.append(
            PlanEntry(
                key=item.key,
                kind=item.kind,
                title=item.title,
                body_sha256=body_digest(node.body),
                state=definition.for_kind(item.kind).default_state(Category.OPEN),
                parent_key=parent_key,
                awaiting_decision_key=None,
            )
        )
    return BulkPlan(
        project_id=project.id, items=tuple(planned), plan_sha256=plan_digest(entries)
    )


def _parent_slot(
    conn: sqlite3.Connection,
    project_id: int,
    node: BulkItem,
    planned: list[PlannedItem],
    parent: int | None,
) -> tuple[str | None, int]:
    """Check a node's parent; return its key and the first free number under it."""
    if node.kind is ItemKind.BACKLOG:
        raise HierarchyError(BACKLOG_VIA_CAPTURE)
    if parent is None:
        stored = check_parent(conn, project_id, node.kind, node.parent_id)
        return (
            None if stored is None else stored.key,
            peek_number(conn, project_id, stored, node.kind),
        )
    check_child_kind(planned[parent].kind, node.kind)
    return planned[parent].key, 1
