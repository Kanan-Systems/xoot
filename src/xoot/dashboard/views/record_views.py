"""Record responses: one item in full, and one decision with its body."""

import sqlite3

from xoot.dashboard.schemas.decision_view import DecisionView
from xoot.dashboard.schemas.item_view import ItemView
from xoot.dashboard.views.lookup import decision_of, item_of, project_of
from xoot.repositories.item import item_db
from xoot.server.key_book import KeyBook
from xoot.server.render import (
    children_summary,
    decision_detail,
    event_entry,
    item_detail,
)
from xoot.services.decision_reads import owned_decisions
from xoot.services.history_service import recent_events

# The same cuts as item_get, so the panel matches what an agent sees.
RECENT_EVENTS = 10
CHILDREN_MAX = 25
OWNED_DECISIONS_MAX = 50


def item_view(conn: sqlite3.Connection, prefix: str, key: str) -> ItemView:
    """
    Return one item with children, recent events and its decisions.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - key (str): the item key from the path.

    Returns:
        - view (ItemView): the item in full.

    Raises:
        - ApiError: 404, no such project or item.
    """
    item = item_of(conn, project_of(conn, prefix), key)
    book = KeyBook(conn)
    children = item_db.list_children(conn, item.project_id, [item.id])
    return ItemView(
        item=item_detail(book, item),
        children=children_summary(book, children, CHILDREN_MAX),
        events=[
            event_entry(book, e) for e in recent_events(conn, item.id, RECENT_EVENTS)
        ],
        decisions=[
            decision_detail(book, d)
            for d in owned_decisions(conn, item, OWNED_DECISIONS_MAX)
        ],
    )


def decision_view(conn: sqlite3.Connection, prefix: str, key: str) -> DecisionView:
    """
    Return one decision with its body.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - key (str): the decision key from the path.

    Returns:
        - view (DecisionView): the decision.

    Raises:
        - ApiError: 404, no such project or decision.
    """
    decision = decision_of(conn, project_of(conn, prefix), key)
    return DecisionView(decision=decision_detail(KeyBook(conn), decision))
