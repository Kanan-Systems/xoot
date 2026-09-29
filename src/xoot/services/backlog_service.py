"""
Capturing backlog items and covering them with subtasks.

A backlog item is open work found along the way. capture puts it next to
where it was found: on the batch of a subtask or batch, on a goal, or on the
project beside a project-level item. backlog_cover turns one into a subtask
and closes it: in its own batch, in a named batch of its goal, or, for a
project-level item, in a named batch of any goal. An item can also be
resolved without a subtask, by moving it to its done state with
item_update. All of these settle through the completion engine: a capture
reopens a done batch or goal, closing an item may let one complete.
"""

import sqlite3

from xoot.exceptions.backlog_error import BacklogError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.services.id_checks import check_id, check_optional_id
from xoot.services.item_rules import is_closed
from xoot.services.item_service import insert_checked
from xoot.services.item_writer import write_item
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def capture(
    store: Store, project_id: int, found_on_id: int, draft: ItemDraft, ctx: WriteContext
) -> tuple[Item, CompletionReport]:
    """
    Capture a backlog item next to the item it was found on.

    Args:
        - store (Store): the database.
        - project_id (int): the project.
        - found_on_id (int): the item it was found on (any kind).
        - draft (ItemDraft): the title, and the body saying why.
        - ctx (WriteContext): the actor.

    Returns:
        - captured (tuple[Item, CompletionReport]): the new backlog item and
          what the completion engine did.

    Raises:
        - InvalidIdError: an id is not an int id.
        - NotFoundError: the project or the item does not exist.
        - CrossProjectError: the item is in another project.
    """
    check_id("project_id", project_id)
    check_id("found_on_id", found_on_id)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        item = capture_in(scope, project_id, found_on_id, draft)
        return item, scope.report()


def capture_in(
    scope: WriteScope, project_id: int, found_on_id: int, draft: ItemDraft
) -> Item:
    """
    Capture a backlog item; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - project_id (int): the project.
        - found_on_id (int): the item it was found on.
        - draft (ItemDraft): the title and the why.

    Returns:
        - item (Item): the new backlog item, in its kind's open state.

    Raises:
        - NotFoundError: the project or the item does not exist.
        - CrossProjectError: the item is in another project.
    """
    found_on = require_item(scope.conn, found_on_id, project_id)
    request = ItemCreate(
        kind=ItemKind.BACKLOG,
        title=draft.title,
        body=draft.body,
        parent_id=backlog_home(found_on),
        found_on_item_id=found_on.id,
    )
    return insert_checked(scope, project_id, request)


def backlog_home(found_on: Item) -> int | None:
    """
    Choose where a backlog item found on an item sits.

    Args:
        - found_on (Item): the item it was found on.

    Returns:
        - parent_id (int | None): the batch of a subtask, the batch or goal
          itself, or, for a backlog item, that item's own level (None for
          the project).
    """
    if found_on.kind in (ItemKind.SUBTASK, ItemKind.BACKLOG):
        return found_on.parent_id
    return found_on.id


def cover(
    store: Store, backlog_id: int, batch_id: int | None, ctx: WriteContext
) -> tuple[Item, Item, CompletionReport]:
    """
    Turn an open backlog item into a subtask and close it.

    Args:
        - store (Store): the database.
        - backlog_id (int): the backlog item.
        - batch_id (int | None): the batch to cover it in; required when the
          item sits on a goal or on the project, else defaults to its own
          batch.
        - ctx (WriteContext): the actor.

    Returns:
        - covered (tuple[Item, Item, CompletionReport]): the new subtask, the
          closed backlog item and what the completion engine did.

    Raises:
        - BacklogError: the item is not open backlog, or the batch is
          missing, not a batch, or in another goal.
        - InvalidIdError: an id is not an int id.
        - NotFoundError: an item does not exist.
    """
    check_id("backlog_id", backlog_id)
    check_optional_id("batch_id", batch_id)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        subtask, backlog = cover_in(scope, backlog_id, batch_id)
        return subtask, backlog, scope.report()


def cover_in(
    scope: WriteScope, backlog_id: int, batch_id: int | None
) -> tuple[Item, Item]:
    """
    Cover a backlog item; the caller owns the transaction.

    The subtask takes the item's title and body and records it as its
    origin; the item records the subtask and moves to its default done
    state.

    Args:
        - scope (WriteScope): the open write scope.
        - backlog_id (int): the backlog item.
        - batch_id (int | None): the batch to cover it in.

    Returns:
        - covered (tuple[Item, Item]): the new subtask and the closed item.

    Raises:
        - BacklogError: the item is not open backlog, or the batch is
          missing, not a batch, or in another goal.
        - NotFoundError: an item does not exist.
    """
    conn = scope.conn
    backlog = open_backlog_item(scope, backlog_id)
    batch = _cover_batch(scope, backlog, batch_id)
    subtask = insert_checked(
        scope,
        backlog.project_id,
        ItemCreate(
            kind=ItemKind.SUBTASK,
            title=backlog.title,
            body=backlog.body,
            parent_id=batch.id,
            origin_item_id=backlog.id,
        ),
    )
    definition = active_workflow(conn, require_project(conn, backlog.project_id))
    done = definition.definition.for_kind(ItemKind.BACKLOG).default_state(Category.DONE)
    current = require_item(conn, backlog.id)
    closed = write_item(
        scope, current, {"state": done, "covered_by_item_id": subtask.id}
    )
    return subtask, closed


def open_backlog_item(scope: WriteScope, item_id: int) -> Item:
    """
    Fetch an item that must be an open backlog item.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): the item.

    Returns:
        - item (Item): the backlog item.

    Raises:
        - BacklogError: the item is not a backlog item, or is done or dropped.
        - NotFoundError: the item does not exist.
    """
    item = require_item(scope.conn, item_id)
    check_open_backlog(scope.conn, item)
    return item


def check_open_backlog(conn: sqlite3.Connection, item: Item) -> None:
    """
    Refuse anything but an open backlog item.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - item (Item): the item.

    Raises:
        - BacklogError: the item is not a backlog item, or is done or dropped.
    """
    if item.kind is not ItemKind.BACKLOG:
        raise BacklogError(f"{item.key} is not a backlog item")
    definition = active_workflow(conn, require_project(conn, item.project_id))
    if is_closed(definition.definition, item):
        raise BacklogError(f"{item.key} is already done or dropped")


def _cover_batch(scope: WriteScope, backlog: Item, batch_id: int | None) -> Item:
    """
    The batch a cover lands in: the item's own batch unless one is named.

    A goal-level item needs a named batch of that goal; a project-level
    item needs a named batch of any goal of the project.
    """
    conn = scope.conn
    parent = (
        None if backlog.parent_id is None else require_item(conn, backlog.parent_id)
    )
    if batch_id is None:
        if parent is None or parent.kind is ItemKind.GOAL:
            where = "the project" if parent is None else f"goal {parent.key}"
            raise BacklogError(
                f"{backlog.key} sits on {where}; name the batch to cover it in"
            )
        return parent
    batch = require_item(conn, batch_id, backlog.project_id)
    if batch.kind is not ItemKind.BATCH:
        raise BacklogError(f"{batch.key} is not a batch")
    if parent is None:
        return batch
    goal_id = parent.id if parent.kind is ItemKind.GOAL else parent.parent_id
    if batch.parent_id != goal_id:
        goal = require_item(conn, goal_id or 0)
        raise BacklogError(f"batch {batch.key} is not in goal {goal.key}")
    return batch
