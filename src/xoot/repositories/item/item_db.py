"""
SQL access for the item table.

The numbering counters (next_child_number, next_backlog_number and
next_decision_number) are never read into an Item and never written by
update(): only the allocate functions move them, so a stale Item can never
roll a counter back.
"""

import sqlite3
from collections.abc import Sequence
from typing import Literal

from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.new_item import NewItem

type Counter = Literal[
    "next_child_number", "next_backlog_number", "next_decision_number"
]

_COLUMNS = (
    "id, project_id, kind, number, key, parent_id, title, body, state, "
    "found_on_item_id, covered_by_item_id, origin_item_id, awaiting_decision_id, "
    "version, created_at, updated_at"
)
_ITEM_COLUMNS = ", ".join(f"item.{name.strip()}" for name in _COLUMNS.split(","))
# Fixed statements per counter: column names are never built from input.
_ALLOCATE: dict[Counter, str] = {
    "next_child_number": (
        "UPDATE item SET next_child_number = next_child_number + 1 "
        "WHERE id = ? RETURNING next_child_number - 1"
    ),
    "next_backlog_number": (
        "UPDATE item SET next_backlog_number = next_backlog_number + 1 "
        "WHERE id = ? RETURNING next_backlog_number - 1"
    ),
    "next_decision_number": (
        "UPDATE item SET next_decision_number = next_decision_number + 1 "
        "WHERE id = ? RETURNING next_decision_number - 1"
    ),
}
_PEEK: dict[Counter, str] = {
    name: f"SELECT {name} FROM item WHERE id = ?" for name in _ALLOCATE
}


def insert(conn: sqlite3.Connection, new: NewItem) -> Item:
    """
    Insert an item at version 1.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewItem): the validated row values.

    Returns:
        - item (Item): the stored row.
    """
    params = new.model_dump(mode="json")
    params["parent_kind"] = _parent_kind(conn, new.parent_id)
    row = conn.execute(
        "INSERT INTO item (project_id, kind, number, key, parent_id, parent_kind, "
        "title, body, state, found_on_item_id, covered_by_item_id, origin_item_id, "
        "awaiting_decision_id, version, created_at, updated_at) VALUES "
        "(:project_id, :kind, :number, :key, :parent_id, :parent_kind, :title, "
        ":body, :state, :found_on_item_id, :covered_by_item_id, :origin_item_id, "
        f":awaiting_decision_id, 1, :created_at, :created_at) RETURNING {_COLUMNS}",
        params,
    ).fetchone()
    return Item.model_validate(dict(row))


def get(conn: sqlite3.Connection, item_id: int) -> Item | None:
    """
    Fetch an item by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): item id.

    Returns:
        - item (Item | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE id = ?", (item_id,)
    ).fetchone()
    return None if row is None else Item.model_validate(dict(row))


def get_by_key(conn: sqlite3.Connection, project_id: int, key: str) -> Item | None:
    """
    Fetch an item by its current key within a project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - key (str): e.g. "goal-1/batch-2".

    Returns:
        - item (Item | None): the item, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? AND key = ?",
        (project_id, key),
    ).fetchone()
    return None if row is None else Item.model_validate(dict(row))


def update(conn: sqlite3.Connection, item: Item, expected_version: int) -> None:
    """
    Write an item's mutable columns, guarded by its previous version.

    kind and project_id never change; number, key and parent change only
    when the item moves.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - item (Item): the new row values, version already bumped.
        - expected_version (int): the version being replaced.

    Raises:
        - StaleWriteError: no row had that id and version.
    """
    params = item.model_dump(mode="json")
    params["expected_version"] = expected_version
    params["parent_kind"] = _parent_kind(conn, item.parent_id)
    cursor = conn.execute(
        "UPDATE item SET number = :number, key = :key, parent_id = :parent_id, "
        "parent_kind = :parent_kind, title = :title, body = :body, "
        "state = :state, found_on_item_id = :found_on_item_id, "
        "covered_by_item_id = :covered_by_item_id, origin_item_id = :origin_item_id, "
        "awaiting_decision_id = :awaiting_decision_id, version = :version, "
        "updated_at = :updated_at WHERE id = :id AND version = :expected_version",
        params,
    )
    if cursor.rowcount != 1:
        raise StaleWriteError(f"item {item.id} changed during the transaction")


def allocate(conn: sqlite3.Connection, item_id: int, counter: Counter) -> int:
    """
    Take the next number from one of an item's counters.

    Must run inside the write transaction that uses the number, so the
    counter and the numbered row commit or roll back together.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - item_id (int): the numbering item.
        - counter (Counter): which counter.

    Returns:
        - number (int): the allocated number.
    """
    return int(conn.execute(_ALLOCATE[counter], (item_id,)).fetchone()[0])


def peek(conn: sqlite3.Connection, item_id: int, counter: Counter) -> int:
    """
    Read the number a counter would hand out next, without taking it.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): the numbering item.
        - counter (Counter): which counter.

    Returns:
        - number (int): the next number.
    """
    return int(conn.execute(_PEEK[counter], (item_id,)).fetchone()[0])


def list_for_project(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List every item of a project, by key.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - items (list[Item]): all items.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_roots(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List a project's top-level items: goals, then the project backlog.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - items (list[Item]): items without a parent, goals first, by number.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? AND parent_id IS NULL "
        "ORDER BY kind = 'backlog', number",
        (project_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_children(
    conn: sqlite3.Connection, project_id: int, parent_ids: Sequence[int]
) -> list[Item]:
    """
    List the direct children of several parents: work first, then backlog.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - parent_ids (Sequence[int]): parent item ids (bounded by callers).

    Returns:
        - items (list[Item]): the children, by parent, backlog last, number.
    """
    if not parent_ids:
        return []
    # Only "?" placeholders are generated; the ids stay bound parameters.
    placeholders = ", ".join("?" for _ in parent_ids)
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? "
        f"AND parent_id IN ({placeholders}) "
        "ORDER BY parent_id, kind = 'backlog', number",
        (project_id, *parent_ids),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_children_of_kind(
    conn: sqlite3.Connection, parent_id: int, kind: ItemKind
) -> list[Item]:
    """
    List one parent's children of one kind, by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - parent_id (int): the parent item id.
        - kind (ItemKind): the child kind.

    Returns:
        - items (list[Item]): the children.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE parent_id = ? AND kind = ? "
        "ORDER BY number",
        (parent_id, kind.value),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_project_backlog(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List the backlog items that sit on the project itself, by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - items (list[Item]): the project backlog.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? AND parent_id IS NULL "
        "AND kind = 'backlog' ORDER BY number",
        (project_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_descendants(conn: sqlite3.Connection, root_id: int) -> list[Item]:
    """
    List every item below a root (not the root itself), parents first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - root_id (int): the subtree root.

    Returns:
        - items (list[Item]): all descendants, shallower keys first.
    """
    rows = conn.execute(
        "WITH RECURSIVE below(id, depth) AS ("
        " SELECT id, 1 FROM item WHERE parent_id = ?"
        " UNION ALL SELECT item.id, below.depth + 1 FROM item"
        " JOIN below ON item.parent_id = below.id"
        f") SELECT {_ITEM_COLUMNS} FROM item JOIN below ON item.id = below.id "
        "ORDER BY below.depth, item.id",
        (root_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def _parent_kind(conn: sqlite3.Connection, parent_id: int | None) -> str | None:
    """The stored kind of a parent, for the kind-pinning foreign key."""
    if parent_id is None:
        return None
    row = conn.execute("SELECT kind FROM item WHERE id = ?", (parent_id,)).fetchone()
    return None if row is None else str(row[0])
