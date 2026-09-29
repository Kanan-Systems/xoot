"""
Backlog reads: backlog items by level, open counts, and what open backlog
blocks.

Every function takes a connection inside the caller's read transaction, so
a view built from several of them sees one snapshot. Nothing here imports
the MCP server; the MCP tools, the CLI and the dashboard share these.
"""

import sqlite3

from xoot.models.item.backlog_level import BacklogLevel
from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.services.item_rules import is_closed
from xoot.services.lookups import active_workflow, require_project
from xoot.utils.keys import SEPARATOR

_LEVELS: dict[int, BacklogLevel] = {0: "project", 1: "goal", 2: "batch"}
_CHILD_KIND = {ItemKind.GOAL: ItemKind.BATCH, ItemKind.BATCH: ItemKind.SUBTASK}


def backlog_level(item: Item) -> BacklogLevel:
    """
    Tell where a backlog item sits, from its key.

    Args:
        - item (Item): a backlog item.

    Returns:
        - level (BacklogLevel): project, goal or batch.
    """
    return _LEVELS[item.key.count(SEPARATOR)]


def backlog_items(
    conn: sqlite3.Connection,
    project_id: int,
    at: Item | None = None,
    include_closed: bool = False,
) -> list[Item]:
    """
    List backlog items: all of a project, or those sitting on one item.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project.
        - at (Item | None): a goal or batch whose own backlog to list; the
          whole project when None.
        - include_closed (bool): also list done and dropped items.

    Returns:
        - items (list[Item]): project level first, then by key.

    Raises:
        - NotFoundError: the project or its workflow is missing.
    """
    definition = _definition(conn, project_id)
    if at is None:
        rows = [
            i
            for i in item_db.list_for_project(conn, project_id)
            if i.kind is ItemKind.BACKLOG
        ]
    else:
        rows = item_db.list_children_of_kind(conn, at.id, ItemKind.BACKLOG)
    shown = [i for i in rows if include_closed or not is_closed(definition, i)]
    return sorted(shown, key=lambda i: (i.key.count(SEPARATOR), i.key))


def backlog_counts(
    conn: sqlite3.Connection, project_id: int
) -> dict[BacklogLevel, int]:
    """
    Count open backlog items per level.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project.

    Returns:
        - counts (dict[BacklogLevel, int]): every level, 0 when empty.
    """
    counts: dict[BacklogLevel, int] = {"project": 0, "goal": 0, "batch": 0}
    for item in backlog_items(conn, project_id):
        counts[backlog_level(item)] += 1
    return counts


def blocked_items(conn: sqlite3.Connection, project_id: int) -> list[BlockedItem]:
    """
    List the open goals and batches held open only by open backlog.

    Every child is done or dropped (and there is at least one), yet open
    backlog items sit on the item, so the completion engine leaves it open.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project.

    Returns:
        - blocked (list[BlockedItem]): by key, with the open backlog count.
    """
    definition = _definition(conn, project_id)
    items = item_db.list_for_project(conn, project_id)
    children: dict[int, list[Item]] = {}
    for item in items:
        if item.parent_id is not None:
            children.setdefault(item.parent_id, []).append(item)
    blocked = []
    for item in items:
        if item.kind not in _CHILD_KIND or is_closed(definition, item):
            continue
        below = children.get(item.id, [])
        work = [c for c in below if c.kind is _CHILD_KIND[item.kind]]
        backlog = [
            c
            for c in below
            if c.kind is ItemKind.BACKLOG and not is_closed(definition, c)
        ]
        if work and backlog and all(is_closed(definition, c) for c in work):
            blocked.append(BlockedItem(key=item.key, open_backlog=len(backlog)))
    return sorted(blocked, key=lambda b: b.key)


def _definition(conn: sqlite3.Connection, project_id: int) -> WorkflowDefinition:
    return active_workflow(conn, require_project(conn, project_id)).definition
