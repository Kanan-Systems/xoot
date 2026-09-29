"""
Subtree drop and reparent, each as a pure preview plus an apply.

The preview runs in a read-only snapshot and returns the planned changes.
The apply re-plans under the write lock (the tree may have changed since the
preview). With a confirm token it refuses a plan that differs from the one
the preview showed; otherwise it writes exactly the fresh plan. A reparent
re-keys the moved subtree (see move_planner) and records every old key as
an alias. Every write settles through the completion engine.
"""

import sqlite3
from collections.abc import Callable
from functools import partial

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.exceptions.state_error import StateError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.repositories.item import item_db
from xoot.services.completion_service import settle
from xoot.services.confirm_service import check_plan, consume_token, plan_digest
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id, check_optional_id
from xoot.services.item_rules import check_parent
from xoot.services.item_store import allocate_number
from xoot.services.item_writer import apply_changes, plan_change
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.move_planner import plan_move
from xoot.services.plan_entries import item_entry
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

type Planner = Callable[[sqlite3.Connection, Item], SubtreePlan]

BACKLOG_MOVES = "backlog items move with backlog_push or backlog_cover"


def preview_drop(store: Store, item_id: int, state: str | None = None) -> SubtreePlan:
    """
    Plan dropping an item and everything under it; writes nothing.

    Done and already-dropped items keep their state.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - state (str | None): the dropped state to use; each kind's default
          dropped state when None.

    Returns:
        - plan (SubtreePlan): the items that would move to a dropped state.

    Raises:
        - StateError: state is not in the root kind's dropped category.
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.read() as conn:
        return _plan_drop(conn, require_item(conn, item_id), state)


# Six arguments: the five of the original apply plus the requested state.
def apply_drop(  # pylint: disable=too-many-arguments
    store: Store,
    item_id: int,
    expected_version: int,
    ctx: WriteContext,
    confirm: Confirmation | None = None,
    *,
    state: str | None = None,
) -> tuple[SubtreePlan, CompletionReport]:
    """
    Drop an item and everything under it.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): the actor.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.
        - state (str | None): the dropped state to use; each kind's default
          dropped state when None.

    Returns:
        - dropped (tuple[SubtreePlan, CompletionReport]): the changes that
          were written and what the completion engine did.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - StateError: state is not in the root kind's dropped category.
        - VersionConflictError: the root changed since expected_version.
        - InvalidIdError: item_id or expected_version is not an int.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        plan = apply_drop_in(scope, item_id, expected_version, confirm, state=state)
        return plan, scope.report()


def apply_drop_in(
    scope: WriteScope,
    item_id: int,
    expected_version: int,
    confirm: Confirmation | None = None,
    *,
    state: str | None = None,
) -> SubtreePlan:
    """
    Drop an item and everything under it; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): the subtree root.
        - expected_version (int): the root version the caller read.
        - confirm (Confirmation | None): a token from the preview, consumed
          in the caller's transaction when given.
        - state (str | None): the dropped state to use; each kind's default
          dropped state when None.

    Returns:
        - plan (SubtreePlan): the changes that were written.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - StateError: state is not in the root kind's dropped category.
        - VersionConflictError: the root changed since expected_version.
        - NotFoundError: no such item.
    """
    planner = partial(_plan_drop, state=state)
    return write_plan(scope, item_id, expected_version, planner, confirm, hold=True)


def preview_reparent(
    store: Store, item_id: int, new_parent_id: int | None
) -> SubtreePlan:
    """
    Plan moving an item, with its descendants, under a new parent.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent.

    Returns:
        - plan (SubtreePlan): the root's and each descendant's key change.

    Raises:
        - HierarchyError: the new parent is not allowed for the root's kind,
          or the root is a backlog item.
        - CrossProjectError: the new parent is in another project.
        - InvalidIdError: item_id or new_parent_id is not an int id.
        - NotFoundError: the item or the new parent does not exist.
    """
    check_id("item_id", item_id)
    check_optional_id("new_parent_id", new_parent_id)
    with store.read() as conn:
        return _plan_reparent(conn, require_item(conn, item_id), new_parent_id)


# Six arguments: the five of the original apply plus the optional confirm.
def apply_reparent(  # pylint: disable=too-many-arguments
    store: Store,
    item_id: int,
    new_parent_id: int | None,
    expected_version: int,
    ctx: WriteContext,
    *,
    confirm: Confirmation | None = None,
) -> tuple[SubtreePlan, CompletionReport]:
    """
    Move an item, with its descendants, under a new parent.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): the actor.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.

    Returns:
        - moved (tuple[SubtreePlan, CompletionReport]): the changes written
          and what the completion engine did.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - VersionConflictError: the root changed since expected_version.
        - HierarchyError: the new parent is not allowed for the root's kind.
        - CrossProjectError: the new parent is in another project.
        - InvalidIdError: an id or expected_version is not an int.
        - NotFoundError: the item or the new parent does not exist.
    """
    check_id("item_id", item_id)
    check_optional_id("new_parent_id", new_parent_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        plan = apply_reparent_in(
            scope, item_id, new_parent_id, expected_version, confirm=confirm
        )
        return plan, scope.report()


def apply_reparent_in(
    scope: WriteScope,
    item_id: int,
    new_parent_id: int | None,
    expected_version: int,
    *,
    confirm: Confirmation | None = None,
) -> SubtreePlan:
    """
    Move an item and its descendants; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent.
        - expected_version (int): the root version the caller read.
        - confirm (Confirmation | None): a token from the preview, consumed
          in the caller's transaction when given.

    Returns:
        - plan (SubtreePlan): the change that was written.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - VersionConflictError: the root changed since expected_version.
        - HierarchyError: the new parent is not allowed for the root's kind.
        - CrossProjectError: the new parent is in another project.
        - NotFoundError: the item or the new parent does not exist.
    """
    planner = partial(_plan_reparent, new_parent_id=new_parent_id)
    return write_plan(scope, item_id, expected_version, planner, confirm)


# Six arguments: the scope, root, version, planner, token and hold flag.
def write_plan(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    scope: WriteScope,
    item_id: int,
    expected_version: int | None,
    planner: Planner,
    confirm: Confirmation | None,
    hold: bool = False,
) -> SubtreePlan:
    """
    Spend the token, re-plan under the write lock, check the plan, write it.

    The token is spent first, inside the write, so it is used only if the
    write commits. A move takes its new number from the new parent here,
    which is the number its plan peeked. A held plan (a drop) keeps the
    completion engine off the items it writes, so nothing it drops is first
    completed; the engine then settles once above the root.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): the plan's root.
        - expected_version (int | None): the root version the caller read;
          None skips the check (the plan digest pins the root instead).
        - planner (Planner): builds the plan from the current rows.
        - confirm (Confirmation | None): the preview's token, if any.
        - hold (bool): keep the engine off the plan's own items.

    Returns:
        - plan (SubtreePlan): the plan that was written.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - VersionConflictError: the root changed since expected_version.
        - StaleWriteError: the new parent handed out another number.
    """
    conn = scope.conn
    root = require_item(conn, item_id)
    token = None if confirm is None else consume_token(conn, confirm, root.project_id)
    if expected_version is not None:
        ensure_version(conn, EntityType.ITEM, root, expected_version)
    plan = planner(conn, root)
    check_plan(token, plan.plan_sha256)
    moves = [c for c in plan.changes if c.item_id == root.id and "key" in c.after]
    if moves:
        _take_number(scope, root, moves[0])
    if not hold:
        apply_changes(scope, plan.changes)
        return plan
    scope.held.update(change.item_id for change in plan.changes)
    try:
        apply_changes(scope, plan.changes)
    finally:
        scope.held.clear()
    settle(scope, require_item(conn, root.id))
    return plan


def _take_number(scope: WriteScope, root: Item, change: ItemChange) -> None:
    """
    Allocate the moved root's number from its new parent's counter.

    Taken whenever the root's key changes, even when the new number equals
    the old one (the diff then omits "number"), so the counter never hands
    that number out again.
    """
    parent_id = change.after.get("parent_id", root.parent_id)
    parent = None if parent_id is None else require_item(scope.conn, parent_id)
    number = allocate_number(scope, root.project_id, parent, root.kind)
    planned = int(str(change.after["key"]).rpartition("-")[2])
    if number != planned:
        raise StaleWriteError("the new parent's numbering moved during the write")


def _plan_drop(
    conn: sqlite3.Connection, root: Item, state: str | None = None
) -> SubtreePlan:
    """
    Drop every live item of the subtree into the requested dropped state.

    The request is checked against the root's kind; a descendant whose kind
    has no dropped state of that name takes its own kind's default instead.
    Items are dropped deepest first, root last, so the completion engine
    never sees a closed parent above children that are still open.
    """
    definition = active_workflow(
        conn, require_project(conn, root.project_id)
    ).definition
    if (
        state is not None
        and definition.for_kind(root.kind).category_of(state) is not Category.DROPPED
    ):
        raise StateError(f"state {state!r} is not a dropped state")
    changes: list[ItemChange] = []
    entries: list[PlanEntry] = []
    for item in reversed([root, *item_db.list_descendants(conn, root.id)]):
        workflow = definition.for_kind(item.kind)
        if workflow.category_of(item.state) in TERMINAL_CATEGORIES:
            continue
        target = (
            state
            if state is not None and workflow.category_of(state) is Category.DROPPED
            else workflow.default_state(Category.DROPPED)
        )
        fields = {"state": target}
        change = plan_change(item, fields)
        if change is not None:
            changes.append(change)
            entries.append(item_entry(conn, item, fields))
    return SubtreePlan(
        root_id=root.id, changes=tuple(changes), plan_sha256=plan_digest(entries)
    )


def _plan_reparent(
    conn: sqlite3.Connection, root: Item, new_parent_id: int | None
) -> SubtreePlan:
    if root.kind is ItemKind.BACKLOG:
        raise HierarchyError(BACKLOG_MOVES)
    parent = check_parent(conn, root.project_id, root.kind, new_parent_id)
    return plan_move(conn, root, parent)
