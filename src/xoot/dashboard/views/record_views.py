"""Record responses: one item in full and one decision with its body."""

import sqlite3

from xoot.dashboard.errors import not_found
from xoot.dashboard.schemas.decision_view import DecisionView
from xoot.dashboard.schemas.item_view import ItemView
from xoot.dashboard.views.lookup import item_of
from xoot.exceptions.not_found_error import NotFoundError
from xoot.repositories.item import item_db
from xoot.server.key_book import KeyBook
from xoot.server.render import (
    children_summary,
    decision_detail,
    event_entry,
    item_detail,
    session_summary,
)
from xoot.services.decision_reads import decision_detail as find_decision
from xoot.services.decision_reads import scoped_decisions
from xoot.services.history_service import recent_events
from xoot.services.session_reads import item_sessions

# The same cuts as item_get, so the panel matches what an agent sees.
RECENT_EVENTS = 10
CHILDREN_MAX = 25
SCOPED_DECISIONS_MAX = 50


def item_view(conn: sqlite3.Connection, key: str) -> ItemView:
    """
    Return one item with children, recent events, sessions and decisions.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - key (str): the item key from the path.

    Returns:
        - view (ItemView): the item in full.

    Raises:
        - ApiError: 404, no such item.
    """
    item = item_of(conn, key)
    book = KeyBook(conn)
    children = item_db.list_children(conn, item.project_id, [item.id])
    return ItemView(
        item=item_detail(book, item),
        children=children_summary(book, children, CHILDREN_MAX),
        events=[
            event_entry(book, e) for e in recent_events(conn, item.id, RECENT_EVENTS)
        ],
        sessions=[session_summary(book, s) for s in item_sessions(conn, item.id)],
        decisions=[
            decision_detail(book, d)
            for d in scoped_decisions(conn, item, SCOPED_DECISIONS_MAX)
        ],
    )


def decision_view(conn: sqlite3.Connection, key: str) -> DecisionView:
    """
    Return one decision with its body.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - key (str): the decision key from the path.

    Returns:
        - view (DecisionView): the decision.

    Raises:
        - ApiError: 404, no such decision.
    """
    try:
        decision = find_decision(conn, key)
    except NotFoundError as exc:
        raise not_found(key) from exc
    return DecisionView(decision=decision_detail(KeyBook(conn), decision))
