"""
Subtree drop and reparent, each as a pure preview plus an apply.

The preview runs in a read-only snapshot and returns the planned changes.
The apply re-plans under the write lock (the tree may have changed since the
preview). With a confirm token it refuses a plan that differs from the one
the preview showed; otherwise it writes exactly the fresh plan.
"""

import sqlite3
from collections.abc import Callable
from functools import partial

from xoot.exceptions.state_error import StateError
from xoot.models.confirm.confirm_token import ConfirmToken
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.repositories.item import item_db
from xoot.services.confirm_service import check_plan, consume_token, plan_digest
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id, check_optional_id
from xoot.services.item_rules import check_parent
from xoot.services.item_writer import apply_changes, plan_change
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.plan_entries import item_entry
from xoot.services.session_links import link_items, open_session_for
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

type Planner = Callable[[sqlite3.Connection, Item], SubtreePlan]


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
) -> SubtreePlan:
    """
    Drop an item and everything under it.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): actor and optional session (changed items are
          linked).
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.
        - state (str | None): the dropped state to use; each kind's default
          dropped state when None.

    Returns:
        - plan (SubtreePlan): the changes that were written.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - StateError: state is not in the root kind's dropped category.
        - VersionConflictError: the root changed since expected_version.
        - SessionStateError: the session is closed.
        - InvalidIdError: item_id or expected_version is not an int.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    check_id("expected_version", expected_version)
    planner = partial(_plan_drop, state=state)
    with store.write() as conn:
        token = _consume(conn, confirm, ctx)
        return _write_plan(conn, item_id, expected_version, ctx, planner, token=token)


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


# Six arguments: the five of the original apply plus the optional confirm.
def apply_reparent(  # pylint: disable=too-many-arguments
    store: Store,
    item_id: int,
    new_parent_id: int | None,
    expected_version: int,
    ctx: WriteContext,
    *,
    confirm: Confirmation | None = None,
) -> SubtreePlan:
    """
    Move an item, with its descendants, under a new parent.

    Args:
        - store (Store): the database.
        - item_id (int): the subtree root.
        - new_parent_id (int | None): the new parent; None unfiles a subtask.
        - expected_version (int): the root version the caller read.
        - ctx (WriteContext): actor and optional session.
        - confirm (Confirmation | None): a token from the preview, consumed
          in this transaction when given.

    Returns:
        - plan (SubtreePlan): the change that was written.

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
    planner = partial(_plan_reparent, new_parent_id=new_parent_id)
    with store.write() as conn:
        token = _consume(conn, confirm, ctx)
        return _write_plan(conn, item_id, expected_version, ctx, planner, token=token)


def _consume(
    conn: sqlite3.Connection, confirm: Confirmation | None, ctx: WriteContext
) -> ConfirmToken | None:
    """Spend the preview's token first, so it is used only if the write commits."""
    if confirm is None:
        return None
    return consume_token(conn, confirm, ctx.session_id)


# The five inputs of the locked re-plan plus the token its plan must match.
def _write_plan(  # pylint: disable=too-many-arguments
    conn: sqlite3.Connection,
    item_id: int,
    expected_version: int,
    ctx: WriteContext,
    planner: Planner,
    *,
    token: ConfirmToken | None,
) -> SubtreePlan:
    """Re-plan under the write lock, check it against the token, then write it."""
    root = require_item(conn, item_id)
    ensure_version(conn, EntityType.ITEM, root, expected_version)
    session = open_session_for(conn, root.project_id, ctx.session_id)
    plan = planner(conn, root)
    check_plan(token, plan.plan_sha256)
    scope = WriteScope(conn, ctx)
    apply_changes(scope, plan.changes)
    link_items(scope, session, [change.item_id for change in plan.changes])
    return plan


def _plan_drop(
    conn: sqlite3.Connection, root: Item, state: str | None = None
) -> SubtreePlan:
    """
    Drop every live item of the subtree into the requested dropped state.

    The request is checked against the root's kind; a descendant whose kind
    has no dropped state of that name takes its own kind's default instead.
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
    for item in [root, *item_db.list_descendants(conn, root.id)]:
        workflow = definition.for_kind(item.kind)
        if workflow.category_of(item.state) in TERMINAL_CATEGORIES:
            continue
        target = (
            state
            if state is not None and workflow.category_of(state) is Category.DROPPED
            else workflow.default_state(Category.DROPPED)
        )
        fields = {"state": target, "backlog_session_id": None}
        change = plan_change(item, fields)
        if change is not None:
            changes.append(change)
            entries.append(item_entry(conn, item, fields))
    return SubtreePlan(
        root_id=root.id,
        changes=tuple(changes),
        carried_item_ids=(),
        plan_sha256=plan_digest(entries),
    )


def _plan_reparent(
    conn: sqlite3.Connection, root: Item, new_parent_id: int | None
) -> SubtreePlan:
    check_parent(conn, root.project_id, root.kind, new_parent_id)
    fields = {"parent_id": new_parent_id}
    change = plan_change(root, fields)
    descendants = item_db.list_descendants(conn, root.id)
    # Descendants keep their own rows, but the digest still pins which move.
    entries = [
        item_entry(conn, root, fields),
        *(item_entry(conn, item, {}) for item in descendants),
    ]
    return SubtreePlan(
        root_id=root.id,
        changes=() if change is None else (change,),
        carried_item_ids=tuple(item.id for item in descendants),
        plan_sha256=plan_digest(entries),
    )
