"""An existing database is backed up before it takes a pending migration."""

import os
import sqlite3
import stat
from pathlib import Path

import pytest

from xoot.exceptions.foreign_key_check_error import ForeignKeyCheckError
from xoot.store import migrator
from xoot.store.backup import backup_path
from xoot.store.connection import connect
from xoot.store.migrator import (
    check_foreign_keys,
    load_migrations,
    migrate,
    user_version,
)
from xoot.store.store import Store

EXTRA = (3, "CREATE TABLE extra (x INTEGER) STRICT;")
MORE = (4, "CREATE TABLE more (x INTEGER) STRICT;")


def _with(monkeypatch: pytest.MonkeyPatch, *extra: tuple[int, str]) -> None:
    shipped = load_migrations()
    monkeypatch.setattr(migrator, "load_migrations", lambda: [*shipped, *extra])


def _projects(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [row[0] for row in conn.execute("SELECT key_prefix FROM project")]
    finally:
        conn.close()


def test_fresh_database_is_not_backed_up(db_path: Path) -> None:
    """A new file has nothing to lose, so no copy is written."""
    Store.open(db_path).close()
    assert not backup_path(db_path, 2).exists()
    assert not list(db_path.parent.glob("*.pre-v*"))


@pytest.mark.usefixtures("project")
def test_backup_before_a_future_migration(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, store: Store
) -> None:
    """The copy holds the data as it was, with mode 0600, named after the target."""
    store.close()
    _with(monkeypatch, EXTRA)
    with Store.open(db_path) as opened:
        assert user_version(opened.conn) == 3
    copy = backup_path(db_path, 3)
    assert copy.name == "xoot.db.pre-v3"
    assert stat.S_IMODE(os.stat(copy).st_mode) == 0o600
    assert _projects(copy) == ["xoot"]
    raw = sqlite3.connect(copy)
    try:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {row[0] for row in raw.execute("SELECT name FROM sqlite_schema")}
        assert "extra" not in tables
    finally:
        raw.close()


def test_only_the_latest_backup_is_kept(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second migration replaces the earlier copy."""
    Store.open(db_path).close()
    _with(monkeypatch, EXTRA)
    Store.open(db_path).close()
    assert backup_path(db_path, 3).exists()
    _with(monkeypatch, EXTRA, MORE)
    Store.open(db_path).close()
    assert not backup_path(db_path, 3).exists()
    assert backup_path(db_path, 4).exists()


def test_up_to_date_database_takes_no_backup(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With nothing pending, no copy is made."""
    Store.open(db_path).close()
    _with(monkeypatch, EXTRA)
    Store.open(db_path).close()
    os.unlink(backup_path(db_path, 3))
    Store.open(db_path).close()
    assert not backup_path(db_path, 3).exists()


def test_backup_never_follows_a_planted_symlink(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An old copy that is a symlink is removed as a link, its target untouched."""
    Store.open(db_path).close()
    target = tmp_path / "elsewhere"
    target.write_text("keep", encoding="utf-8")
    os.symlink(target, backup_path(db_path, 3))
    _with(monkeypatch, EXTRA)
    Store.open(db_path).close()
    assert target.read_text(encoding="utf-8") == "keep"
    assert not backup_path(db_path, 3).is_symlink()


def test_foreign_key_check_passes_on_a_clean_database(store: Store) -> None:
    """The helper is silent when every reference resolves."""
    check_foreign_keys(store.conn)


def test_foreign_key_check_names_the_tables(tmp_path: Path) -> None:
    """Dangling references are refused by table name, never by row content."""
    conn = connect(tmp_path / "fk.db")
    try:
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY) STRICT")
        conn.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, "
            "parent_id INTEGER REFERENCES parent (id)) STRICT"
        )
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("INSERT INTO child VALUES (1, 42)")
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(ForeignKeyCheckError) as caught:
            check_foreign_keys(conn)
        assert caught.value.tables == ("child",)
        assert "42" not in str(caught.value)
    finally:
        conn.close()


def test_migration_leaving_dangling_rows_rolls_back(db_path: Path) -> None:
    """A table rebuild that breaks a reference never commits."""
    Store.open(db_path).close()
    rebuild = (
        3,
        "PRAGMA defer_foreign_keys = ON;"
        "CREATE TABLE ref (id INTEGER PRIMARY KEY, "
        "item_id INTEGER REFERENCES item (id)) STRICT;"
        "INSERT INTO ref VALUES (1, 999);",
    )
    shipped = load_migrations()
    conn = connect(db_path)
    try:
        with pytest.raises(ForeignKeyCheckError):
            migrate(conn, [*shipped, rebuild])
        assert user_version(conn) == 2
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_schema")}
        assert "ref" not in tables
    finally:
        conn.close()
