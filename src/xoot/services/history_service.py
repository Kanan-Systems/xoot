"""
Event reads: an entity's recent history and a project's change marker.

Functions take a connection inside the caller's read transaction.
"""

import sqlite3

from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.repositories.event import event_db
from xoot.services.id_checks import check_id


def recent_events(conn: sqlite3.Connection, item_id: int, limit: int) -> list[Event]:
    """
    Return an item's most recent events, newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - item_id (int): the item id.
        - limit (int): the most events to return.

    Returns:
        - events (list[Event]): up to limit events.

    Raises:
        - InvalidIdError: item_id is not an int id.
    """
    check_id("item_id", item_id)
    events = event_db.list_for_entity(conn, EntityType.ITEM, item_id)
    return events[::-1][:limit]


def latest_event_id(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Return the id of the project's newest event.

    Every write appends an event, so a poller that sees this value change
    knows the project changed, without reading anything else.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): the project id.

    Returns:
        - event_id (int): the highest event id, 0 with no events.

    Raises:
        - InvalidIdError: project_id is not an int id.
    """
    check_id("project_id", project_id)
    return event_db.latest_id(conn, project_id)
