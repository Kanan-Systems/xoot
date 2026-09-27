"""
sqlite3 errors never escape a service or Store.open raw; they are
re-raised as XootErrors with the driver error chained as __cause__.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from xoot.exceptions.database_access_error import DatabaseAccessError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.store_open_error import StoreOpenError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services import project_service
from xoot.services.item_service import create_item, get_item
from xoot.store.store import Store


def test_integrity_error_in_a_write_is_translated_and_rolled_back(
    store: Store, project: Project
) -> None:
    """The constraint error surfaces as IntegrityViolationError; nothing commits."""
    with pytest.raises(IntegrityViolationError, match="UNIQUE") as caught:
        with store.write() as conn:
            conn.execute("UPDATE project SET name = 'renamed'")
            conn.execute(
                "INSERT INTO project_alias (alias, project_id) VALUES ('xo', ?)",
                (project.id,),
            )
    assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)
    assert caught.value.sqlite_errorname == "SQLITE_CONSTRAINT_PRIMARYKEY"
    assert project_service.get_project(store, project.id).name == "xoot"


def test_service_constraint_failure_is_translated(
    monkeypatch: pytest.MonkeyPatch,
    store: Store,
    project: Project,
    ctx: WriteContext,
) -> None:
    """With the service's own check bypassed, the schema's refusal is an XootError."""
    monkeypatch.setattr(project_service, "require_free_alias", lambda *_: None)
    with pytest.raises(IntegrityViolationError) as caught:
        project_service.add_alias(store, project.id, "xo", ctx)
    assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)


def test_write_inside_a_read_is_translated(store: Store) -> None:
    """A write attempted in a read-only snapshot fails as DatabaseAccessError."""
    with pytest.raises(DatabaseAccessError) as caught:
        with store.read() as conn:
            conn.execute("UPDATE project SET name = 'x'")
    assert isinstance(caught.value.__cause__, sqlite3.OperationalError)


def test_closed_store_errors_are_translated(
    store: Store, project: Project, ctx: WriteContext
) -> None:
    """Reads and writes on a closed store raise DatabaseAccessError, not sqlite3."""
    store.close()
    with pytest.raises(DatabaseAccessError) as read_error:
        get_item(store, 1)
    with pytest.raises(DatabaseAccessError) as write_error:
        create_item(store, project.id, ItemCreate(kind=ItemKind.GOAL, title="t"), ctx)
    for error in (read_error.value, write_error.value):
        assert isinstance(error.__cause__, sqlite3.ProgrammingError)


def test_checkpoint_errors_are_translated(store: Store) -> None:
    """The WAL checkpoint used by redaction is guarded the same way."""
    assert store.checkpoint() is True
    store.close()
    with pytest.raises(DatabaseAccessError):
        store.checkpoint()


def test_open_of_a_non_database_file_is_translated(db_path: Path) -> None:
    """A private file that is not SQLite fails as StoreOpenError naming it."""
    db_path.parent.mkdir(mode=0o700)
    fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, b"not a database, just some private bytes " * 64)
    finally:
        os.close(fd)
    with pytest.raises(StoreOpenError) as caught:
        Store.open(db_path)
    assert (
        str(caught.value) == f"could not open the database at {db_path} (SQLITE_NOTADB)"
    )
    assert caught.value.path == db_path
    assert isinstance(caught.value.__cause__, sqlite3.DatabaseError)
