"""
Plan entries: the post-apply form of each item a two-phase plan touches.

Bulk, drop, reparent and close all digest their plans through here, so every
plan pins the same columns in the same form, and a preview and its apply can
only match when they would leave every affected item identical.
"""

import sqlite3
from typing import Any

from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.item.item import Item
from xoot.models.session.disposition import Disposition
from xoot.services.lookups import (
    require_decision,
    require_item,
    require_project,
    require_session,
)
from xoot.utils.utils import body_digest, session_key


def item_entry(
    conn: sqlite3.Connection,
    item: Item,
    fields: dict[str, Any],
    disposition: Disposition | None = None,
) -> PlanEntry:
    """
    Describe an existing item as it will stand once the plan is written.

    Args:
        - conn (sqlite3.Connection): connection inside the plan's snapshot.
        - item (Item): the current row.
        - fields (dict[str, Any]): every field the plan sets on it.
        - disposition (Disposition | None): the close disposition, if any.

    Returns:
        - entry (PlanEntry): the item's post-apply columns.

    Raises:
        - NotFoundError: a referenced parent, session or decision is missing.
    """
    after = item.model_copy(update=fields)
    parent_key = (
        None
        if after.parent_id is None
        else require_item(conn, after.parent_id, after.project_id).key
    )
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
        backlog_session_key=_session_key(conn, after),
        awaiting_decision_key=decision_key,
        disposition=disposition,
    )


def _session_key(conn: sqlite3.Connection, item: Item) -> str | None:
    if item.backlog_session_id is None:
        return None
    session = require_session(conn, item.backlog_session_id, item.project_id)
    prefix = require_project(conn, item.project_id).key_prefix
    return session_key(prefix, session.number)
