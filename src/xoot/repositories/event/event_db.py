"""
SQL access for the append-only event table.

Deliberately exposes no general update and no delete. The one rewrite is
redact(), which touches only before, after and redacted_at; the schema's
triggers refuse anything else.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.new_event import NewEvent
from xoot.models.fields import format_timestamp

_COLUMNS = (
    "id, project_id, entity_type, entity_id, action, actor_kind, client, "
    "session_id, before, after, created_at, redacted_at"
)


def append(conn: sqlite3.Connection, new: NewEvent) -> Event:
    """
    Append one event.

    Args:
        - conn (sqlite3.Connection): connection inside the write transaction
          of the mutation the event describes.
        - new (NewEvent): the validated row values.

    Returns:
        - event (Event): the stored row.
    """
    params = new.model_dump(mode="json")
    params["before"] = _to_json(params["before"])
    params["after"] = _to_json(params["after"])
    row = conn.execute(
        "INSERT INTO event (project_id, entity_type, entity_id, action, actor_kind, "
        "client, session_id, before, after, created_at) VALUES (:project_id, "
        ":entity_type, :entity_id, :action, :actor_kind, :client, :session_id, "
        f":before, :after, :created_at) RETURNING {_COLUMNS}",
        params,
    ).fetchone()
    return _to_event(row)


def redact(
    conn: sqlite3.Connection,
    event_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    redacted_at: datetime,
) -> None:
    """
    Replace an event's before/after with scrubbed copies and stamp it.

    Args:
        - conn (sqlite3.Connection): connection inside the redaction's write
          transaction.
        - event_id (int): the event to rewrite.
        - before (dict[str, Any] | None): the scrubbed before values.
        - after (dict[str, Any] | None): the scrubbed after values.
        - redacted_at (datetime): the redaction time.
    """
    conn.execute(
        "UPDATE event SET before = ?, after = ?, redacted_at = ? WHERE id = ?",
        (_to_json(before), _to_json(after), format_timestamp(redacted_at), event_id),
    )


def list_for_entity(
    conn: sqlite3.Connection, entity_type: EntityType, entity_id: int
) -> list[Event]:
    """
    List an entity's events, oldest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - entity_type (EntityType): entity type.
        - entity_id (int): entity id.

    Returns:
        - events (list[Event]): the events.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM event WHERE entity_type = ? AND entity_id = ? "
        "ORDER BY id",
        (entity_type.value, entity_id),
    ).fetchall()
    return [_to_event(row) for row in rows]


def list_after_version(
    conn: sqlite3.Connection, entity_type: EntityType, entity_id: int, version: int
) -> list[Event]:
    """
    List the events that moved a versioned entity past a version.

    Args:
        - conn (sqlite3.Connection): open connection.
        - entity_type (EntityType): item or decision.
        - entity_id (int): entity id.
        - version (int): the version the caller last saw.

    Returns:
        - events (list[Event]): events whose after-version is greater.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM event WHERE entity_type = ? AND entity_id = ? "
        "AND json_extract(after, '$.version') > ? ORDER BY id",
        (entity_type.value, entity_id, version),
    ).fetchall()
    return [_to_event(row) for row in rows]


def list_for_project(conn: sqlite3.Connection, project_id: int) -> list[Event]:
    """
    List a project's events, oldest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - events (list[Event]): the events.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM event WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()
    return [_to_event(row) for row in rows]


def latest_id(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Return the id of a project's newest event.

    Event ids only grow, so a changed value means the project changed.
    The event_project index answers this without reading the table.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.

    Returns:
        - event_id (int): the highest event id, or 0 with no events.
    """
    row = conn.execute(
        "SELECT coalesce(max(id), 0) FROM event WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return int(row[0])


def _to_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _to_event(row: sqlite3.Row) -> Event:
    values: dict[str, Any] = dict(row)
    for column in ("before", "after"):
        if values[column] is not None:
            values[column] = json.loads(values[column])
    return Event.model_validate(values)
