"""T2: migrations apply in order, once, safely across processes."""

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from xoot.exceptions.migration_error import MigrationError
from xoot.exceptions.migration_failed_error import MigrationFailedError
from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.store import migrator
from xoot.store.connection import connect
from xoot.store.migrator import load_migrations, migrate, order_migrations, user_version
from xoot.store.paths import prepare_db_file
from xoot.store.store import Store

PROCESSES = 4
BROKEN = [(1, "CREATE TABLE a (x INTEGER) STRICT; SELECT nope();")]


def _open_and_report(db_path: str, barrier: Any, results: Any) -> None:
    """Spawned worker: open the same fresh DB at the same moment as the others."""
    barrier.wait(timeout=60)
    with Store.open(Path(db_path)) as store:
        results.put(user_version(store.conn))


def _schema(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return conn.execute(
        "SELECT name, sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY name"
    ).fetchall()


def test_shipped_migrations_apply(db_path: Path) -> None:
    """A fresh store is at the newest version and every table is STRICT."""
    latest = load_migrations()[-1][0]
    with Store.open(db_path) as store:
        assert user_version(store.conn) == latest
        tables = store.conn.execute(
            "SELECT name, strict FROM pragma_table_list "
            "WHERE schema = 'main' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    assert {name for name, _ in tables} == {
        "project", "project_alias", "project_path", "workflow", "item",
        "session", "session_item_ref", "decision", "event", "confirm_token",
    }  # fmt: skip
    assert all(strict == 1 for _, strict in tables)


def test_apply_in_order(tmp_path: Path) -> None:
    """Each migration builds on the previous one, lowest version first."""
    migrations = order_migrations(
        [
            ("0002_add.sql", "ALTER TABLE a ADD COLUMN y INTEGER;"),
            ("0001_create.sql", "CREATE TABLE a (x INTEGER) STRICT;"),
        ]
    )
    assert [version for version, _ in migrations] == [1, 2]
    conn = connect(tmp_path / "xoot.db")
    try:
        assert migrate(conn, migrations) == 2
        columns = [row[1] for row in conn.execute("PRAGMA table_info(a)")]
        assert columns == ["x", "y"]
    finally:
        conn.close()


def test_second_run_is_a_noop(store: Store) -> None:
    """Migrating an up-to-date DB changes nothing."""
    before = (_schema(store.conn), store.conn.total_changes)
    assert migrate(store.conn) == load_migrations()[-1][0]
    assert (_schema(store.conn), store.conn.total_changes) == before


def _assert_no_sql(error: Exception) -> None:
    message = str(error)
    assert not any(token in message for token in ("CREATE", "SELECT", "nope"))


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    """
    A migration that fails midway leaves neither its tables nor its version,
    and surfaces as MigrationFailedError (driver error chained, no SQL text).
    """
    conn = connect(tmp_path / "xoot.db")
    try:
        with pytest.raises(MigrationFailedError) as caught:
            migrate(conn, BROKEN)
        assert user_version(conn) == 0
        assert _schema(conn) == []
    finally:
        conn.close()
    assert caught.value.version == 1
    assert str(caught.value) == "migrating to schema version 1 failed (SQLITE_ERROR)"
    assert isinstance(caught.value.__cause__, sqlite3.OperationalError)
    _assert_no_sql(caught.value)


def test_unreadable_version_is_translated(tmp_path: Path) -> None:
    """Reading user_version on a closed connection fails as MigrationFailedError."""
    conn = connect(tmp_path / "xoot.db")
    conn.close()
    with pytest.raises(MigrationFailedError, match="reading the schema version"):
        user_version(conn)


def test_store_open_surfaces_migration_failures(
    monkeypatch: pytest.MonkeyPatch, db_path: Path
) -> None:
    """Store.open lets MigrationFailedError through, never a raw sqlite3 error."""
    monkeypatch.setattr(migrator, "load_migrations", lambda: BROKEN)
    with pytest.raises(MigrationFailedError) as caught:
        Store.open(db_path)
    assert isinstance(caught.value.__cause__, sqlite3.OperationalError)
    _assert_no_sql(caught.value)


@pytest.mark.parametrize(
    "names",
    [["0001_a.sql", "0003_c.sql"], ["0002_b.sql"], ["0001_a.sql", "0001_b.sql"]],
)
def test_gaps_and_duplicates_are_rejected(names: list[str]) -> None:
    """Versions must run 1, 2, 3... so no file can be skipped silently."""
    with pytest.raises(MigrationError, match="contiguous"):
        order_migrations([(name, "") for name in names])


@pytest.mark.parametrize("name", ["1_a.sql", "0001-a.sql", "0001_A.sql"])
def test_bad_names_are_rejected(name: str) -> None:
    """Only NNNN_lowercase_name.sql is accepted."""
    with pytest.raises(MigrationError, match="invalid"):
        order_migrations([(name, "")])


def test_concurrent_processes_all_succeed(db_path: Path, spawn_workers: Any) -> None:
    """Several processes opening one fresh DB at once all end up migrated."""
    versions = spawn_workers(_open_and_report, [(str(db_path),)] * PROCESSES)
    assert versions == [load_migrations()[-1][0]] * PROCESSES


def test_version_is_rechecked_under_the_lock(db_path: Path) -> None:
    """
    A migrator that read the old version, then waited for the lock while
    another connection migrated, must skip instead of re-running the SQL.
    """
    migrations = load_migrations()
    prepare_db_file(db_path)
    holder = connect(db_path)
    outcome: dict[str, Any] = {}
    traced: list[str] = []
    stale_read_done = threading.Event()

    def on_statement(sql: str) -> None:
        traced.append(sql)
        # migrate() reads user_version before it asks for the lock, so by
        # the time BEGIN IMMEDIATE starts the stale read has happened.
        if sql == "BEGIN IMMEDIATE":
            stale_read_done.set()

    def late_migrator() -> None:
        conn = connect(db_path)
        conn.set_trace_callback(on_statement)
        try:
            outcome["version"] = migrate(conn, migrations)
        except sqlite3.Error as exc:
            outcome["error"] = exc
        finally:
            conn.close()

    try:
        holder.execute("BEGIN IMMEDIATE")
        thread = threading.Thread(target=late_migrator)
        thread.start()
        assert stale_read_done.wait(timeout=30)
        for version, sql in migrations:
            holder.executescript(sql)
            holder.execute(f"PRAGMA user_version = {version}")
        holder.execute("COMMIT")
        thread.join(timeout=30)
    finally:
        holder.close()
    assert outcome == {"version": migrations[-1][0]}
    assert "PRAGMA user_version" in traced[: traced.index("BEGIN IMMEDIATE")]
    assert not any(sql.lstrip().startswith("CREATE") for sql in traced)


def test_newer_database_is_refused(db_path: Path) -> None:
    """A DB whose user_version is ahead of the code will not open."""
    Store.open(db_path).close()
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA user_version = 999")
    raw.close()
    with pytest.raises(SchemaVersionError) as caught:
        Store.open(db_path)
    assert caught.value.found == 999
    assert caught.value.known == load_migrations()[-1][0]
