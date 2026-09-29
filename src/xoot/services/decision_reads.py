"""
Decision reads for views: one decision with its body, and the decisions
made on an item.

Functions take a connection inside the caller's read transaction.
"""

import sqlite3

from xoot.models.decision.decision import Decision
from xoot.models.item.item import Item
from xoot.repositories.decision import decision_db
from xoot.services import key_resolver


def decision_detail(conn: sqlite3.Connection, project_id: int, key: str) -> Decision:
    """
    Fetch one decision, body included, by its key within a project.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project.
        - key (str): the unqualified decision key as the caller sent it.

    Returns:
        - decision (Decision): the decision with its body.

    Raises:
        - NotFoundError: the key is malformed or names no decision.
    """
    return key_resolver.decision_by_key(conn, project_id, key)


def owned_decisions(conn: sqlite3.Connection, item: Item, limit: int) -> list[Decision]:
    """
    List the decisions made on an item, newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - item (Item): the owner item.
        - limit (int): the most decisions to return.

    Returns:
        - decisions (list[Decision]): up to limit decisions.
    """
    return decision_db.list_for_owner(conn, item.id, limit)
