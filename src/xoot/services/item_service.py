"""
Creating and updating single items.

Numbers come from the parent's counter inside the write transaction, so
concurrent writers get unique keys. Every write settles the goals and
batches above it (see completion_service); the store-level functions return
the write's completion report beside the row.
"""

from typing import Any

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.workflow.category import Category
from xoot.services.completion_service import check_manual_done
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id
from xoot.services.item_rules import (
    check_awaited_decision,
    check_parent,
    check_state,
    check_transition,
)
from xoot.services.item_writer import insert_item, write_item
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

BACKLOG_VIA_CAPTURE = "backlog items are created with capture"


def create_item(
    store: Store, project_id: int, request: ItemCreate, ctx: WriteContext
) -> tuple[Item, CompletionReport]:
    """
    Create a goal, batch or subtask.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - request (ItemCreate): validated item details.
        - ctx (WriteContext): the actor.

    Returns:
        - created (tuple[Item, CompletionReport]): the new item and what the
          completion engine did (a new subtask reopens a done batch).

    Raises:
        - HierarchyError: the parent is not allowed for this kind, or the
          kind is backlog.
        - StateError: the state is not in the workflow.
        - CrossProjectError: a reference is in another project.
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or a reference does not exist.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        item = create_item_in(scope, project_id, request)
        return item, scope.report()


def create_item_in(scope: WriteScope, project_id: int, request: ItemCreate) -> Item:
    """
    Create a goal, batch or subtask; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - project_id (int): project id.
        - request (ItemCreate): validated item details.

    Returns:
        - item (Item): the new item.

    Raises:
        - HierarchyError: the parent is not allowed for this kind, or the
          kind is backlog.
        - StateError: the state is not in the workflow.
        - CrossProjectError: a reference is in another project.
        - NotFoundError: the project or a reference does not exist.
    """
    if request.kind is ItemKind.BACKLOG:
        raise HierarchyError(BACKLOG_VIA_CAPTURE)
    return insert_checked(scope, project_id, request)


def insert_checked(scope: WriteScope, project_id: int, request: ItemCreate) -> Item:
    """
    Validate a create of any kind against the rows and insert it.

    Args:
        - scope (WriteScope): the open write scope.
        - project_id (int): project id.
        - request (ItemCreate): item details; state defaults to open.

    Returns:
        - item (Item): the new item.

    Raises:
        - HierarchyError: the parent is not allowed for this kind.
        - StateError: the state is not in the workflow.
        - CrossProjectError: a reference is in another project.
        - NotFoundError: the project or a reference does not exist.
    """
    conn = scope.conn
    project = require_project(conn, project_id)
    workflow = active_workflow(conn, project).definition.for_kind(request.kind)
    check_parent(conn, project_id, request.kind, request.parent_id)
    state = request.state or workflow.default_state(Category.OPEN)
    check_state(workflow, state)
    check_awaited_decision(conn, project_id, request.awaiting_decision_id)
    return insert_item(scope, project, request.model_copy(update={"state": state}))


def update_item(
    store: Store,
    item_id: int,
    expected_version: int,
    changes: ItemUpdate,
    ctx: WriteContext,
) -> tuple[Item, CompletionReport]:
    """
    Change an item's title, body, state or awaited decision.

    Args:
        - store (Store): the database.
        - item_id (int): item id.
        - expected_version (int): the version the caller read.
        - changes (ItemUpdate): the fields to change.
        - ctx (WriteContext): the actor.

    Returns:
        - updated (tuple[Item, CompletionReport]): the stored item and what
          the completion engine did.

    Raises:
        - VersionConflictError: the item changed since expected_version.
        - StateError: unknown state or disallowed transition.
        - OpenChildrenError: a done state was asked for on a goal or batch
          with open work or open backlog under it.
        - CrossProjectError: a reference is in another project.
        - InvalidIdError: item_id or expected_version is not an int.
        - NotFoundError: the item or a reference does not exist.
    """
    check_id("item_id", item_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        item = update_item_in(scope, item_id, expected_version, changes)
        return item, scope.report()


def update_item_in(
    scope: WriteScope, item_id: int, expected_version: int, changes: ItemUpdate
) -> Item:
    """
    Change an item; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): item id.
        - expected_version (int): the version the caller read.
        - changes (ItemUpdate): the fields to change.

    Returns:
        - item (Item): the stored item.

    Raises:
        - VersionConflictError: the item changed since expected_version.
        - StateError: unknown state or disallowed transition.
        - OpenChildrenError: a done state was asked for on a goal or batch
          with open work or open backlog under it.
        - CrossProjectError: a reference is in another project.
        - NotFoundError: the item or a reference does not exist.
    """
    conn = scope.conn
    item = require_item(conn, item_id)
    ensure_version(conn, EntityType.ITEM, item, expected_version)
    project = require_project(conn, item.project_id)
    definition = active_workflow(conn, project).definition
    workflow = definition.for_kind(item.kind)
    fields: dict[str, Any] = changes.provided()
    state = fields.get("state", item.state)
    check_state(workflow, state)
    check_transition(workflow, item.state, state)
    if "state" in fields:
        check_manual_done(conn, definition, item, state)
    check_awaited_decision(conn, item.project_id, fields.get("awaiting_decision_id"))
    return write_item(scope, item, fields)


def get_item(store: Store, item_id: int) -> Item:
    """
    Fetch an item.

    Args:
        - store (Store): the database.
        - item_id (int): item id.

    Returns:
        - item (Item): the item.

    Raises:
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.read() as conn:
        return require_item(conn, item_id)
