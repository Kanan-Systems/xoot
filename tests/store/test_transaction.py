"""Write transactions commit or roll back as a unit; reads cannot write."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from xoot.store.connection import connect
from xoot.store.transaction import read_transaction, write_transaction


@pytest.fixture(name="conn")
def fixture_conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A verified connection with one scratch table."""
    conn = connect(tmp_path / "xoot.db")
    conn.execute("CREATE TABLE t (x INTEGER) STRICT")
    try:
        yield conn
    finally:
        conn.close()


def _count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM t").fetchone()[0])


def test_commits_on_success(conn: sqlite3.Connection) -> None:
    """Rows written in the block are committed."""
    with write_transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
    assert not conn.in_transaction
    assert _count(conn) == 1


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt])
def test_rolls_back_on_any_exception(
    conn: sqlite3.Connection, error: type[BaseException]
) -> None:
    """Any exception, even a non-Exception one, rolls back and propagates."""
    with pytest.raises(error):
        with write_transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            raise error
    assert not conn.in_transaction
    assert _count(conn) == 0


def test_takes_the_write_lock_immediately(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """BEGIN IMMEDIATE holds the lock before any write, blocking other writers."""
    other = sqlite3.connect(tmp_path / "xoot.db", autocommit=True, timeout=0)
    try:
        with write_transaction(conn):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
    finally:
        other.close()


def test_read_transaction_refuses_writes(conn: sqlite3.Connection) -> None:
    """Writes fail inside a read transaction, and writing works again after."""
    with read_transaction(conn):
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO t VALUES (1)")
    assert not conn.in_transaction
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 0
    with write_transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
    assert _count(conn) == 1
