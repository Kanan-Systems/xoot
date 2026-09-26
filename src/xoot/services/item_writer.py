"""
Planning and writing item changes.

Every item mutation, whatever service drives it, goes through write_item so
it is re-validated, version-bumped and recorded the same way.
"""

from collections.abc import Sequence
from typing import Any

from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.repositories.item import item_db
from xoot.services.lookups import require_item
from xoot.services.write_scope import WriteScope, changed_fields


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
    before, after = changed_fields(item, _merged(item, fields))
    if not after:
        return None
    return ItemChange(item_id=item.id, key=item.key, before=before, after=after)


def write_item(scope: WriteScope, item: Item, fields: dict[str, Any]) -> Item:
    """
    Apply field changes to one item: validate, bump version, store, record.

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
    candidate = _merged(item, fields)
    if candidate == item:
        return item
    updated = candidate.model_copy(
        update={"version": item.version + 1, "updated_at": scope.now}
    )
    item_db.update(scope.conn, updated, item.version)
    scope.updated(item, updated)
    return updated


def apply_changes(scope: WriteScope, changes: Sequence[ItemChange]) -> list[Item]:
    """
    Write planned changes, re-reading each item first.

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


def _merged(item: Item, fields: dict[str, Any]) -> Item:
    return Item.model_validate({**item.model_dump(), **fields})
