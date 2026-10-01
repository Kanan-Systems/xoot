"""
The supported schema version is a constant in code, not the migration files
found on disk: a process left running across an upgrade sees the new files
but must still refuse the newer database it cannot read.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.store import migrator
from xoot.store.migrator import (
    SCHEMA_VERSION,
    latest_version,
    load_migrations,
    user_version,
)
from xoot.store.store import Store


def test_constant_matches_the_highest_migration_file() -> None:
    """A new migration file without a bumped SCHEMA_VERSION fails here."""
    assert latest_version() == SCHEMA_VERSION


def test_constant_is_three() -> None:
    """This release supports schema version 3; the entry-path tests rely on it."""
    assert SCHEMA_VERSION == 3


def test_newer_database_is_refused_with_the_constant(
    newer_database: Callable[[], int], db_path: Path
) -> None:
    """A database one version past the constant does not open."""
    found = newer_database()
    with pytest.raises(SchemaVersionError) as caught:
        Store.open(db_path)
    assert (caught.value.found, caught.value.known) == (found, SCHEMA_VERSION)
    assert str(caught.value) == (
        f"database schema version {found} is newer than supported {SCHEMA_VERSION}"
    )


def test_old_process_refuses_after_the_files_were_replaced(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The stale-process case: code that supports version 2 finds version 3's
    files on disk (the install replaced them) and a database at 3. It
    refuses instead of reading rows its models do not know.
    """
    Store.open(db_path).close()
    monkeypatch.setattr(migrator, "SCHEMA_VERSION", 2)
    with pytest.raises(SchemaVersionError) as caught:
        Store.open(db_path)
    assert (caught.value.found, caught.value.known) == (3, 2)


def test_files_above_the_constant_are_not_applied(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A migration file the code does not support never runs."""
    shipped = load_migrations()
    future = (SCHEMA_VERSION + 1, "CREATE TABLE future (x INTEGER) STRICT;")
    monkeypatch.setattr(migrator, "load_migrations", lambda: [*shipped, future])
    with Store.open(db_path) as store:
        assert user_version(store.conn) == SCHEMA_VERSION
        tables = {
            row[0] for row in store.conn.execute("SELECT name FROM sqlite_schema")
        }
    assert "future" not in tables
