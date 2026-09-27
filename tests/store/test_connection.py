"""Connections get the safety pragmas and fail closed when they do not."""

import sqlite3
from pathlib import Path

import pytest

from xoot.exceptions.pragma_check_error import PragmaCheckError
from xoot.store import connection
from xoot.store.connection import connect, verify_pragmas


def test_pragmas_are_applied(tmp_path: Path) -> None:
    """foreign_keys, WAL, busy_timeout, synchronous and secure_delete are in effect."""
    conn = connect(tmp_path / "xoot.db")
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        # 1 is NORMAL.
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
        assert conn.execute("PRAGMA secure_delete").fetchone()[0] == 1
        assert conn.autocommit is True
    finally:
        conn.close()


def test_journal_mode_mismatch_fails_closed() -> None:
    """An in-memory database cannot use WAL, so the read-back rejects it."""
    with pytest.raises(PragmaCheckError, match="journal_mode=memory"):
        connect(Path(":memory:"))


def test_foreign_keys_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If foreign keys end up off, the connection is refused."""
    monkeypatch.setattr(
        connection,
        "PRAGMAS",
        ("PRAGMA foreign_keys = OFF", "PRAGMA journal_mode = WAL"),
    )
    with pytest.raises(PragmaCheckError, match="foreign_keys=0"):
        connect(tmp_path / "xoot.db")


@pytest.mark.parametrize(("value", "reads_back"), [("OFF", 0), ("FAST", 2)])
def test_secure_delete_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str, reads_back: int
) -> None:
    """Anything but secure_delete=1 is refused; FAST skips some freed pages."""
    pragmas = tuple(
        f"PRAGMA secure_delete = {value}" if "secure_delete" in p else p
        for p in connection.PRAGMAS
    )
    monkeypatch.setattr(connection, "PRAGMAS", pragmas)
    with pytest.raises(PragmaCheckError, match=f"secure_delete={reads_back}"):
        connect(tmp_path / "xoot.db")


def test_verify_rejects_default_connection(tmp_path: Path) -> None:
    """A plain sqlite3 connection (driver defaults) does not pass."""
    conn = sqlite3.connect(tmp_path / "plain.db")
    try:
        with pytest.raises(PragmaCheckError):
            verify_pragmas(conn)
    finally:
        conn.close()
