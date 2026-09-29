"""A database from xoot 0.2 is refused on open and never touched."""

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from xoot.cli.__main__ import main
from xoot.cli.exit_codes import UNAVAILABLE
from xoot.exceptions.legacy_database_error import LegacyDatabaseError
from xoot.store.connection import connect
from xoot.store.migrator import migrate
from xoot.store.paths import prepare_db_file
from xoot.store.store import Store


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_file(db_path: Path, version: int, journal: str) -> Path:
    """A 0.2-shaped file: a session table and schema version 1 (or 0)."""
    prepare_db_file(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute(f"PRAGMA journal_mode = {journal}")
    raw.execute("CREATE TABLE session (id INTEGER PRIMARY KEY, title TEXT) STRICT")
    raw.execute("INSERT INTO session (title) VALUES ('an old session')")
    raw.execute(f"PRAGMA user_version = {version}")
    raw.commit()
    raw.close()
    return db_path


@pytest.mark.parametrize("journal", ["wal", "delete"])
@pytest.mark.parametrize("version", [1, 0])
def test_v02_file_is_refused_and_left_byte_identical(
    db_path: Path, version: int, journal: str
) -> None:
    """Version 1, or any file holding a session table, is refused unchanged."""
    _legacy_file(db_path, version, journal)
    before = _digest(db_path)
    with pytest.raises(LegacyDatabaseError, match="xoot 0.2 or earlier"):
        Store.open(db_path)
    assert _digest(db_path) == before
    assert not db_path.with_name(db_path.name + "-wal").exists()


def test_version_1_alone_is_refused(db_path: Path) -> None:
    """Schema version 1 is the 0.2 schema even without the table."""
    prepare_db_file(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA user_version = 1")
    raw.close()
    with pytest.raises(LegacyDatabaseError):
        Store.open(db_path)


def test_message_says_what_to_do(db_path: Path) -> None:
    """The message names the version, the change and the fix, not the path."""
    _legacy_file(db_path, 1, "wal")
    with pytest.raises(LegacyDatabaseError) as caught:
        Store.open(db_path)
    message = str(caught.value)
    assert "data model changed" in message
    assert "Move the file aside" in message
    assert "xoot init" in message
    assert str(db_path) not in message


def test_migrator_refuses_too(db_path: Path) -> None:
    """migrate() itself refuses a legacy connection, as a second line."""
    _legacy_file(db_path, 1, "wal")
    conn = connect(db_path)
    try:
        with pytest.raises(LegacyDatabaseError):
            migrate(conn)
    finally:
        conn.close()


def test_cli_exits_3(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI prints the refusal and exits 3, leaving the file as it was."""
    _legacy_file(db_path, 1, "wal")
    before = _digest(db_path)
    assert main(["--db", str(db_path), "project", "list"]) == UNAVAILABLE
    err = capsys.readouterr().err
    assert "LegacyDatabaseError" in err
    assert "xoot 0.2 or earlier" in err
    assert _digest(db_path) == before
    assert oct(os.stat(db_path).st_mode & 0o777) == "0o600"
