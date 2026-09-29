"""
SQL access for the item_alias table.

Aliases are append-only: the schema refuses any update or delete, and an
alias that names a live key.
"""

import sqlite3
from datetime import datetime

from xoot.models.fields import format_timestamp


def insert(
    conn: sqlite3.Connection,
    project_id: int,
    alias_key: str,
    item_id: int,
    created_at: datetime,
) -> None:
    """
    Record an old key of an item.

    Args:
        - conn (sqlite3.Connection): connection inside the write transaction
          that moved the item.
        - project_id (int): the item's project.
        - alias_key (str): the key the item held before the move.
        - item_id (int): the item.
        - created_at (datetime): the move's time.
    """
    conn.execute(
        "INSERT INTO item_alias (project_id, alias_key, item_id, created_at) "
        "VALUES (?, ?, ?, ?)",
        (project_id, alias_key, item_id, format_timestamp(created_at)),
    )


def item_id_for(
    conn: sqlite3.Connection, project_id: int, alias_key: str
) -> int | None:
    """
    Resolve an old key to the item that held it.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - alias_key (str): an old key.

    Returns:
        - item_id (int | None): the item, or None when the key was never an
          alias in this project.
    """
    row = conn.execute(
        "SELECT item_id FROM item_alias WHERE project_id = ? AND alias_key = ?",
        (project_id, alias_key),
    ).fetchone()
    return None if row is None else int(row[0])


def list_for_item(conn: sqlite3.Connection, item_id: int) -> list[str]:
    """
    List every old key of an item, oldest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - item_id (int): the item.

    Returns:
        - keys (list[str]): the alias keys.
    """
    rows = conn.execute(
        "SELECT alias_key FROM item_alias WHERE item_id = ? "
        "ORDER BY created_at, alias_key",
        (item_id,),
    ).fetchall()
    return [str(row[0]) for row in rows]
