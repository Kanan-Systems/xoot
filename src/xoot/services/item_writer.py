"""
Planning and writing item changes.

Every item mutation, whatever service drives it, goes through write_item so
it is re-validated, version-bumped, recorded and settled the same way.
Every insert goes through insert_item, so single, bulk and backlog creates
number, record and settle items identically. Settling is the completion
engine (completion_service), run after each write in the same transaction.
"""

from collections.abc import Sequence
from typing import Any

from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.item_create import ItemCreate
from xoot.models.project.project import Project
from xoot.services.completion_service import settle
from xoot.services.item_store import insert_row, merged, store_changes
from xoot.services.lookups import require_item
from xoot.services.write_scope import WriteScope, changed_fields


def insert_item(scope: WriteScope, project: Project, request: ItemCreate) -> Item:
    """
    Store a new item, then complete or reopen what sits above it.

    The caller has already validated the request, including its state.

    Args:
        - scope (WriteScope): the current write scope.
        - project (Project): the item's project.
        - request (ItemCreate): validated item details with state set.

    Returns:
        - item (Item): the stored item.
    """
    item = insert_row(scope, project, request)
    settle(scope, item)
    return item


def plan_change(item: Item, fields: dict[str, Any]) -> ItemChange | None:
    """
    Describe what setting some fields would change, without writing.

    Args:
        - item (Item): the current row.
        - fields (dict[str, Any]): field name to new value.

    Returns:
        - change (ItemChange | None): the effective change, or None if the
          values are already in place.
    """
    before, after = changed_fields(item, merged(item, fields))
    if not after:
        return None
    return ItemChange(item_id=item.id, key=item.key, before=before, after=after)


def write_item(scope: WriteScope, item: Item, fields: dict[str, Any]) -> Item:
    """
    Apply field changes to one item, then settle what sits above it.

    Args:
        - scope (WriteScope): the current write scope.
        - item (Item): the current row.
        - fields (dict[str, Any]): field name to new value.

    Returns:
        - item (Item): the stored row (unchanged if nothing differed).

    Raises:
        - pydantic.ValidationError: a value breaks the item model.
        - StaleWriteError: the row changed inside the transaction.
    """
    updated = store_changes(scope, item, fields)
    if updated is not item:
        settle(scope, updated, item)
    return updated


def apply_changes(scope: WriteScope, changes: Sequence[ItemChange]) -> list[Item]:
    """
    Write planned changes in order, re-reading each item first.

    Args:
        - scope (WriteScope): the current write scope.
        - changes (Sequence[ItemChange]): changes planned in this transaction.

    Returns:
        - items (list[Item]): the stored rows, in change order.
    """
    return [
        write_item(scope, require_item(scope.conn, change.item_id), change.after)
        for change in changes
    ]
