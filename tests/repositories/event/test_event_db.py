"""
The event log is append-only in the repository and in the database; the
only rewrite either allows is a redaction of before/after.
"""

import inspect
import sqlite3
from collections.abc import Iterator

import pytest

from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.models.event.entity_type import EntityType
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.store.store import Store

STAMP = "'2026-01-01T00:00:00.000000Z'"
FIRST = "WHERE id = (SELECT min(id) FROM event)"


@pytest.fixture(name="raw")
def fixture_raw(store: Store, project: Project) -> Iterator[sqlite3.Connection]:
    """A plain sqlite3 connection to the store's file: direct SQL, no xoot."""
    assert project.id
    conn = sqlite3.connect(store.path, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def test_repository_exposes_no_general_update_or_delete() -> None:
    """The public functions append, read, or redact before/after."""
    public = {
        name
        for name, member in inspect.getmembers(event_db, inspect.isfunction)
        if not name.startswith("_") and member.__module__ == event_db.__name__
    }
    assert public == {
        "append",
        "redact",
        "list_for_entity",
        "list_after_version",
        "list_for_project",
        "latest_id",
    }


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    "sql", ["UPDATE event SET action = 'update'", "DELETE FROM event"]
)
def test_store_refuses_changes(store: Store, sql: str) -> None:
    """Through the store, the trigger's refusal surfaces as an XootError."""
    with pytest.raises(IntegrityViolationError, match="append-only") as caught:
        with store.write() as conn:
            conn.execute(sql)
    assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)


def test_direct_delete_is_refused(raw: sqlite3.Connection) -> None:
    """DELETE stays forbidden, redacted or not."""
    raw.execute(f"UPDATE event SET redacted_at = {STAMP} {FIRST}")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute("DELETE FROM event")


def test_update_without_redaction_stamp_is_refused(raw: sqlite3.Connection) -> None:
    """Rewriting before/after is only allowed as a stamped redaction."""
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute(f"UPDATE event SET after = json_object('x', 1) {FIRST}")


@pytest.mark.parametrize(
    "assignment",
    [
        "id = id + 1000",
        "project_id = project_id + 1",
        "entity_type = 'decision'",
        "entity_id = entity_id + 1",
        "action = 'update'",
        "actor_kind = 'system'",
        "client = 'chat'",
        "created_at = '2000-01-01T00:00:00.000000Z'",
    ],
)
def test_update_of_any_other_column_is_refused(
    raw: sqlite3.Connection, assignment: str
) -> None:
    """Even with redacted_at set, only before and after may change."""
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute(f"UPDATE event SET {assignment}, redacted_at = {STAMP} {FIRST}")


def test_stamped_payload_rewrite_is_allowed(
    store: Store, raw: sqlite3.Connection, project: Project
) -> None:
    """The redaction shape passes: new after, redacted_at set, all else kept."""
    with store.read() as conn:
        original = event_db.list_for_entity(conn, EntityType.PROJECT, project.id)[0]
    raw.execute(
        f"UPDATE event SET after = json_object('name', '[redacted]'), "
        f"redacted_at = {STAMP} {FIRST}"
    )
    with store.read() as conn:
        rewritten = event_db.list_for_entity(conn, EntityType.PROJECT, project.id)[0]
    assert rewritten.after == {"name": "[redacted]"}
    assert rewritten.redacted_at is not None
    assert rewritten.model_dump(exclude={"after", "redacted_at"}) == (
        original.model_dump(exclude={"after", "redacted_at"})
    )


def test_events_round_trip(store: Store, project: Project) -> None:
    """Stored JSON comes back as the same dicts."""
    with store.read() as conn:
        created = event_db.list_for_entity(conn, EntityType.PROJECT, project.id)[0]
    assert created.before is None
    assert created.after is not None
    assert created.after["key_prefix"] == "xoot"
    assert created.redacted_at is None
