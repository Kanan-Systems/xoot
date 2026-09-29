"""
Pushing a backlog item one level up: batch to goal, goal to project.

A push is a move (see move_planner): the item takes the next backlog number
of its new level and its old key becomes an alias. It is two-phase: the
preview plans the new key, and the apply spends the preview's token, re-plans
under the write lock and refuses a plan that changed. The old level may
complete once the item leaves it; the new one reopens if it was done.
"""

import sqlite3

from xoot.exceptions.backlog_error import BacklogError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.write_context import WriteContext
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.services.backlog_service import check_open_backlog
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_item
from xoot.services.move_planner import plan_move
from xoot.services.subtree_service import write_plan
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def preview_push(store: Store, item_id: int) -> SubtreePlan:
    """
    Plan pushing a backlog item one level up; writes nothing.

    Args:
        - store (Store): the database.
        - item_id (int): the backlog item.

    Returns:
        - plan (SubtreePlan): its parent, number and key change.

    Raises:
        - BacklogError: not an open backlog item, or already on the project.
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.read() as conn:
        return plan_push(conn, require_item(conn, item_id))


def apply_push(
    store: Store, item_id: int, ctx: WriteContext, confirm: Confirmation | None
) -> tuple[SubtreePlan, CompletionReport]:
    """
    Push a backlog item one level up.

    Args:
        - store (Store): the database.
        - item_id (int): the backlog item.
        - ctx (WriteContext): the actor.
        - confirm (Confirmation | None): the preview's token; None only where
          the caller confirmed the plan another way (a paste dry run).

    Returns:
        - pushed (tuple[SubtreePlan, CompletionReport]): the change written
          and what the completion engine did.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - BacklogError: not an open backlog item, or already on the project.
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        plan = apply_push_in(scope, item_id, confirm)
        return plan, scope.report()


def apply_push_in(
    scope: WriteScope, item_id: int, confirm: Confirmation | None
) -> SubtreePlan:
    """
    Push a backlog item one level up; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope.
        - item_id (int): the backlog item.
        - confirm (Confirmation | None): the preview's token, if any.

    Returns:
        - plan (SubtreePlan): the change written.

    Raises:
        - ConfirmTokenError: the token cannot authorize this call, or the
          plan changed since the preview.
        - BacklogError: not an open backlog item, or already on the project.
        - NotFoundError: no such item.
    """
    return write_plan(scope, item_id, None, plan_push, confirm)


def plan_push(conn: sqlite3.Connection, item: Item) -> SubtreePlan:
    """
    Plan one push from the current rows.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - item (Item): the item to push.

    Returns:
        - plan (SubtreePlan): its parent, number and key change.

    Raises:
        - BacklogError: not an open backlog item, or already on the project.
    """
    check_open_backlog(conn, item)
    if item.parent_id is None:
        raise BacklogError(f"{item.key} is on the project; it cannot be pushed further")
    parent = require_item(conn, item.parent_id)
    upper = None if parent.parent_id is None else require_item(conn, parent.parent_id)
    return plan_move(conn, item, upper)
