"""
Decision reads for views: one decision with its body, and the decisions
scoped to an item.

Functions take a connection inside the caller's read transaction.
"""

import sqlite3

from xoot.models.decision.decision import Decision
from xoot.models.item.item import Item
from xoot.repositories.decision import decision_db
from xoot.services import key_resolver


def decision_detail(conn: sqlite3.Connection, key: str) -> Decision:
    """
    Fetch one decision, body included, by its public key.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - key (str): the decision key as the caller sent it.

    Returns:
        - decision (Decision): the decision with its body.

    Raises:
        - NotFoundError: the key is malformed or names no decision.
    """
    return key_resolver.decision_by_key(conn, key)


def scoped_decisions(
    conn: sqlite3.Connection, item: Item, limit: int
) -> list[Decision]:
    """
    List the decisions whose scope is an item, newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - item (Item): the scope item.
        - limit (int): the most decisions to return.

    Returns:
        - decisions (list[Decision]): up to limit decisions.
    """
    return decision_db.list_for_scope(conn, item.project_id, item.id, limit)
