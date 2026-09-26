"""
Explicit transaction scopes for an autocommit connection.

Writes take the write lock up front (BEGIN IMMEDIATE) so a read-then-write
sequence can never be invalidated halfway through by another process.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """
    Run a block in one BEGIN IMMEDIATE transaction.

    Commits when the block finishes, rolls back on any exception
    (including KeyboardInterrupt) and re-raises it.

    Args:
        - conn (sqlite3.Connection): an autocommit connection.

    Returns:
        - conn (Iterator[sqlite3.Connection]): the same connection, in a
          transaction.

    Raises:
        - sqlite3.OperationalError: the write lock was not obtained within
          the busy timeout.
    """
    conn.execute("BEGIN IMMEDIATE")
    committed = False
    try:
        yield conn
        conn.execute("COMMIT")
        committed = True
    finally:
        # SQLite may already have rolled back on some errors (e.g. disk full).
        if not committed and conn.in_transaction:
            conn.execute("ROLLBACK")


@contextmanager
def read_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """
    Run a block in one read-only snapshot.

    query_only makes any write inside the block fail, and the transaction is
    always rolled back, so previews provably write nothing.

    Args:
        - conn (sqlite3.Connection): an autocommit connection.

    Returns:
        - conn (Iterator[sqlite3.Connection]): the same connection, in a
          read-only transaction.
    """
    conn.execute("PRAGMA query_only = ON")
    try:
        conn.execute("BEGIN")
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
    finally:
        conn.execute("PRAGMA query_only = OFF")
