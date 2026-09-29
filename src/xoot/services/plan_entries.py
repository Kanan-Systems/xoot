"""
Plan entries: the post-apply form of each item a two-phase plan touches.

Bulk create, drop, reparent and backlog push all digest their plans through
here, so every plan pins the same columns in the same form, and a preview
and its apply can only match when they would leave every affected item
identical.
"""

import sqlite3
from typing import Any

from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.item.item import Item
from xoot.services.lookups import require_decision, require_item
from xoot.utils.utils import body_digest


def item_entry(
    conn: sqlite3.Connection, item: Item, fields: dict[str, Any]
) -> PlanEntry:
    """
    Describe an existing item as it will stand once the plan is written.

    Args:
        - conn (sqlite3.Connection): connection inside the plan's snapshot.
        - item (Item): the current row.
        - fields (dict[str, Any]): every field the plan sets on it; a move
          also passes "parent_key", the new parent's post-move key, since
          that parent may be moving in the same plan.

    Returns:
        - entry (PlanEntry): the item's post-apply columns.

    Raises:
        - NotFoundError: a referenced parent or decision is missing.
    """
    columns = {name: value for name, value in fields.items() if name != "parent_key"}
    after = item.model_copy(update=columns)
    parent_key = fields.get("parent_key")
    if "parent_key" not in fields and after.parent_id is not None:
        parent_key = require_item(conn, after.parent_id, after.project_id).key
    decision_key = (
        None
        if after.awaiting_decision_id is None
        else require_decision(conn, after.awaiting_decision_id, after.project_id).key
    )
    return PlanEntry(
        key=after.key,
        kind=after.kind,
        title=after.title,
        body_sha256=body_digest(after.body),
        state=after.state,
        parent_key=parent_key,
        awaiting_decision_key=decision_key,
    )
