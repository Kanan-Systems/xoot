"""
Optimistic concurrency: version checks explained from the event log.

Every item or decision update names the version the caller read. On a
mismatch the error lists what changed since then and who changed it.
"""

import sqlite3

from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.repositories.event import event_db


def ensure_version(
    conn: sqlite3.Connection,
    entity_type: EntityType,
    entity: Item | Decision,
    expected_version: int,
) -> None:
    """
    Raise unless the stored version is the one the caller expects.

    Must run inside the write transaction, so no other writer can slip in
    between this check and the update.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - entity_type (EntityType): item or decision.
        - entity (Item | Decision): the current row.
        - expected_version (int): the version the caller read.

    Raises:
        - VersionConflictError: the versions differ.
    """
    if entity.version == expected_version:
        return
    events = event_db.list_after_version(conn, entity_type, entity.id, expected_version)
    fields = sorted(
        {name for e in events for name in (e.after or {}) if name != "version"}
    )
    actors: list[Actor] = []
    for event in events:
        actor = Actor(kind=event.actor_kind, client=event.client)
        if actor not in actors:
            actors.append(actor)
    raise VersionConflictError(entity.key, entity.version, tuple(fields), tuple(actors))
