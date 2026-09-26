"""D9: the event log is append-only in the repository and in the database."""

import inspect
import sqlite3

import pytest

from xoot.models.event.entity_type import EntityType
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.store.store import Store


def test_repository_exposes_no_update_or_delete() -> None:
    """The only public functions append or read."""
    public = {
        name
        for name, member in inspect.getmembers(event_db, inspect.isfunction)
        if not name.startswith("_") and member.__module__ == event_db.__name__
    }
    assert public == {
        "append",
        "list_for_entity",
        "list_after_version",
        "list_for_project",
    }


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    "sql", ["UPDATE event SET action = 'update'", "DELETE FROM event"]
)
def test_database_refuses_changes(store: Store, sql: str) -> None:
    """Even raw SQL cannot rewrite or remove events."""
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with store.write() as conn:
            conn.execute(sql)


def test_events_round_trip(store: Store, project: Project) -> None:
    """Stored JSON comes back as the same dicts."""
    with store.read() as conn:
        created = event_db.list_for_entity(conn, EntityType.PROJECT, project.id)[0]
    assert created.before is None
    assert created.after is not None
    assert created.after["key_prefix"] == "xoot"
