"""
Planning a move: an item and everything under it re-keyed under a new parent.

A key is its parent's key plus its own kind-number segment, and numbers are
allocated by the parent, so a moved item takes the next number of its new
parent and every descendant's key is rebased onto the new key. Descendants
keep their own numbers. The write records each old key as an alias (see
item_store), so every key an item ever held still resolves.
"""

import sqlite3

from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.repositories.item import item_db
from xoot.services.confirm_service import plan_digest
from xoot.services.item_store import peek_number
from xoot.services.item_writer import plan_change
from xoot.services.plan_entries import item_entry
from xoot.utils.keys import child_key, rebase_key


def plan_move(
    conn: sqlite3.Connection, root: Item, new_parent: Item | None
) -> SubtreePlan:
    """
    Plan moving an item, with its descendants, under a new parent.

    The caller has checked the hierarchy. Moving an item to the parent it
    already has plans nothing.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - root (Item): the item to move.
        - new_parent (Item | None): the new parent; None for the project.

    Returns:
        - plan (SubtreePlan): the root's parent, number and key change, then
          each descendant's key change, parents first.
    """
    new_parent_id = None if new_parent is None else new_parent.id
    if new_parent_id == root.parent_id:
        return SubtreePlan(root_id=root.id, changes=(), plan_sha256=plan_digest([]))
    number = peek_number(conn, root.project_id, new_parent, root.kind)
    parent_key = None if new_parent is None else new_parent.key
    new_key = child_key(parent_key, root.kind, number)
    fields = {"parent_id": new_parent_id, "number": number, "key": new_key}
    changes: list[ItemChange] = []
    entries: list[PlanEntry] = []
    _add(conn, root, fields, parent_key, changes, entries)
    for item in item_db.list_descendants(conn, root.id):
        rebased = rebase_key(item.key, root.key, new_key)
        own_parent = rebased.rpartition("/")[0]
        _add(conn, item, {"key": rebased}, own_parent, changes, entries)
    return SubtreePlan(
        root_id=root.id, changes=tuple(changes), plan_sha256=plan_digest(entries)
    )


# Six arguments: the item, its fields and parent key, and the two outputs.
def _add(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    conn: sqlite3.Connection,
    item: Item,
    fields: dict[str, object],
    parent_key: str | None,
    changes: list[ItemChange],
    entries: list[PlanEntry],
) -> None:
    """Append one item's change and its post-move plan entry."""
    change = plan_change(item, fields)
    if change is not None and "number" in fields and "number" not in change.after:
        # The number the item takes is shown even when it happens to be the
        # one it had; writing it again changes nothing.
        change = change.model_copy(
            update={
                "before": {**change.before, "number": item.number},
                "after": {**change.after, "number": fields["number"]},
            }
        )
    if change is not None:
        changes.append(change)
    entries.append(item_entry(conn, item, {**fields, "parent_key": parent_key}))
