"""
SQL access for the append-only event table.

Deliberately exposes no update or delete; the schema's triggers refuse them
as well.
"""

import json
import sqlite3
from typing import Any

from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.new_event import NewEvent

_COLUMNS = (
    "id, project_id, entity_type, entity_id, action, actor_kind, client, "
    "session_id, before, after, created_at"
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
