"""
Subtree drop and reparent, each as a pure preview plus an apply.

The preview runs in a read-only snapshot and returns the planned changes.
The apply re-plans under the write lock (the tree may have changed since the
preview) and writes exactly that plan.
"""

import sqlite3
from collections.abc import Callable
from functools import partial

from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.repositories.item import item_db
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id, check_optional_id
from xoot.services.item_rules import check_parent
from xoot.services.item_writer import apply_changes, plan_change
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.session_links import link_items, open_session_for
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

type Planner = Callable[[sqlite3.Connection, Item], SubtreePlan]


def preview_drop(store: Store, item_id: int) -> SubtreePlan:
    """
    Plan dropping an item and everything under it; writes nothing.

    Done and already-dropped items keep their state.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.

    Returns:
        - plan (SubtreePlan): the items that would move to the default
          dropped state.

    Raises:
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.read() as conn:
        return _plan_drop(conn, require_item(conn, item_id))


def apply_drop(
    store: Store, item_id: int, expected_version: int, ctx: WriteContext
) -> SubtreePlan:
    """
    Drop an item and everything under it.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): actor and optional session (changed items are
          linked).

    Returns:
        - plan (SubtreePlan): the changes that were written.

    Raises:
        - VersionConflictError: the root changed since expected_version.
        - SessionStateError: the session is closed.
        - InvalidIdError: item_id or expected_version is not an int.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    check_id("expected_version", expected_version)
    return _apply(store, item_id, expected_version, ctx, _plan_drop)


def preview_reparent(
    store: Store, item_id: int, new_parent_id: int | None
) -> SubtreePlan:
    """
    Plan moving an item, with its descendants, under a new parent.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent; None unfiles a subtask.

    Returns:
        - plan (SubtreePlan): the root's parent change and the carried
          descendants.

    Raises:
        - HierarchyError: the new parent is not allowed for the root's kind.
        - CrossProjectError: the new parent is in another project.
        - InvalidIdError: item_id or new_parent_id is not an int id.
        - NotFoundError: the item or the new parent does not exist.
    """
    check_id("item_id", item_id)
    check_optional_id("new_parent_id", new_parent_id)
    with store.read() as conn:
        return _plan_reparent(conn, require_item(conn, item_id), new_parent_id)


def apply_reparent(
    store: Store,
    item_id: int,
    new_parent_id: int | None,
    expected_version: int,
    ctx: WriteContext,
) -> SubtreePlan:
    """
    Move an item, with its descendants, under a new parent.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent; None unfiles a subtask.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): actor and optional session.

    Returns:
        - plan (SubtreePlan): the change that was written.

    Raises:
        - VersionConflictError: the root changed since expected_version.
        - HierarchyError: the new parent is not allowed for the root's kind.
        - CrossProjectError: the new parent is in another project.
        - InvalidIdError: an id or expected_version is not an int.
        - NotFoundError: the item or the new parent does not exist.
    """
    check_id("item_id", item_id)
    check_optional_id("new_parent_id", new_parent_id)
    check_id("expected_version", expected_version)
    planner = partial(_plan_reparent, new_parent_id=new_parent_id)
    return _apply(store, item_id, expected_version, ctx, planner)


def _apply(
    store: Store,
    item_id: int,
    expected_version: int,
    ctx: WriteContext,
    planner: Planner,
) -> SubtreePlan:
    """Re-plan under the write lock, then write the plan and its events."""
    with store.write() as conn:
        root = require_item(conn, item_id)
        ensure_version(conn, EntityType.ITEM, root, expected_version)
        session = open_session_for(conn, root.project_id, ctx.session_id)
        plan = planner(conn, root)
        scope = WriteScope(conn, ctx)
        apply_changes(scope, plan.changes)
        link_items(scope, session, [change.item_id for change in plan.changes])
        return plan


def _plan_drop(conn: sqlite3.Connection, root: Item) -> SubtreePlan:
    definition = active_workflow(
        conn, require_project(conn, root.project_id)
    ).definition
    changes: list[ItemChange] = []
    for item in [root, *item_db.list_descendants(conn, root.id)]:
        workflow = definition.for_kind(item.kind)
        if workflow.category_of(item.state) in TERMINAL_CATEGORIES:
            continue
        change = plan_change(
            item,
            {
                "state": workflow.default_state(Category.DROPPED),
                "backlog_session_id": None,
            },
        )
        if change is not None:
            changes.append(change)
    return SubtreePlan(root_id=root.id, changes=tuple(changes), carried_item_ids=())


def _plan_reparent(
    conn: sqlite3.Connection, root: Item, new_parent_id: int | None
) -> SubtreePlan:
    check_parent(conn, root.project_id, root.kind, new_parent_id)
    change = plan_change(root, {"parent_id": new_parent_id})
    carried = tuple(item.id for item in item_db.list_descendants(conn, root.id))
    return SubtreePlan(
        root_id=root.id,
        changes=() if change is None else (change,),
        carried_item_ids=carried,
    )
