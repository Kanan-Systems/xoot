"""SQL access for the item table."""

import sqlite3
from collections.abc import Sequence

from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.models.item.item import Item
from xoot.models.item.new_item import NewItem

_COLUMNS = (
    "id, project_id, number, key, kind, parent_id, title, body, state, "
    "backlog_session_id, awaiting_decision_id, version, created_at, updated_at"
)
_ITEM_COLUMNS = ", ".join(f"item.{name.strip()}" for name in _COLUMNS.split(","))


def insert(conn: sqlite3.Connection, new: NewItem) -> Item:
    """
    Insert an item at version 1.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewItem): the validated row values.

    Returns:
        - item (Item): the stored row.
    """
    row = conn.execute(
        "INSERT INTO item (project_id, number, key, kind, parent_id, title, body, "
        "state, backlog_session_id, awaiting_decision_id, version, created_at, "
        "updated_at) VALUES (:project_id, :number, :key, :kind, :parent_id, :title, "
        ":body, :state, :backlog_session_id, :awaiting_decision_id, 1, :created_at, "
        f":created_at) RETURNING {_COLUMNS}",
        new.model_dump(mode="json"),
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


def get_by_key(conn: sqlite3.Connection, key: str) -> Item | None:
    """
    Fetch an item by its public key.

    Args:
        - conn (sqlite3.Connection): open connection.
        - key (str): e.g. "xoot-12".

    Returns:
        - item (Item | None): the item, or None.
    """
    row = conn.execute(f"SELECT {_COLUMNS} FROM item WHERE key = ?", (key,)).fetchone()
    return None if row is None else Item.model_validate(dict(row))


def update(conn: sqlite3.Connection, item: Item, expected_version: int) -> None:
    """
    Write an item's mutable columns, guarded by its previous version.

    kind, number, key and project_id never change after insert.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - item (Item): the new row values, version already bumped.
        - expected_version (int): the version being replaced.

    Raises:
        - StaleWriteError: no row had that id and version.
    """
    params = item.model_dump(mode="json")
    params["expected_version"] = expected_version
    cursor = conn.execute(
        "UPDATE item SET parent_id = :parent_id, title = :title, body = :body, "
        "state = :state, backlog_session_id = :backlog_session_id, "
        "awaiting_decision_id = :awaiting_decision_id, version = :version, "
        "updated_at = :updated_at WHERE id = :id AND version = :expected_version",
        params,
    )
    if cursor.rowcount != 1:
        raise StaleWriteError(f"item {item.id} changed during the transaction")


def list_for_project(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List every item of a project, by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - items (list[Item]): all items.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? ORDER BY number",
        (project_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_roots(conn: sqlite3.Connection, project_id: int) -> list[Item]:
    """
    List a project's top-level items: goals and unfiled subtasks.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - items (list[Item]): items without a parent, by number.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? AND parent_id IS NULL "
        "ORDER BY number",
        (project_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_children(
    conn: sqlite3.Connection, project_id: int, parent_ids: Sequence[int]
) -> list[Item]:
    """
    List the direct children of several parents, by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - parent_ids (Sequence[int]): parent item ids (bounded by callers).

    Returns:
        - items (list[Item]): the children.
    """
    if not parent_ids:
        return []
    # Only "?" placeholders are generated; the ids stay bound parameters.
    placeholders = ", ".join("?" for _ in parent_ids)
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM item WHERE project_id = ? "
        f"AND parent_id IN ({placeholders}) ORDER BY number",
        (project_id, *parent_ids),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_descendants(conn: sqlite3.Connection, root_id: int) -> list[Item]:
    """
    List every item below a root (not the root itself), by number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - root_id (int): the subtree root.

    Returns:
        - items (list[Item]): all descendants.
    """
    rows = conn.execute(
        "WITH RECURSIVE below(id) AS ("
        " SELECT id FROM item WHERE parent_id = ?"
        " UNION ALL SELECT item.id FROM item JOIN below ON item.parent_id = below.id"
        f") SELECT {_ITEM_COLUMNS} FROM item JOIN below ON item.id = below.id "
        "ORDER BY item.number",
        (root_id,),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]


def list_session_backlogged(
    conn: sqlite3.Connection, project_id: int, closed_before_seq: int | None
) -> list[Item]:
    """
    List items held in the backlog of a closed session of the project.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - closed_before_seq (int | None): only sessions whose close_seq is
          strictly below this sequence value; any closed session when None.

    Returns:
        - items (list[Item]): matching items, by number.
    """
    rows = conn.execute(
        f"SELECT {_ITEM_COLUMNS} FROM item "
        "JOIN session ON session.id = item.backlog_session_id "
        "WHERE item.project_id = ? AND session.status = 'closed' "
        "AND (? IS NULL OR session.close_seq < ?) ORDER BY item.number",
        (project_id, closed_before_seq, closed_before_seq),
    ).fetchall()
    return [Item.model_validate(dict(row)) for row in rows]
