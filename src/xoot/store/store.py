"""
The Store: one open, verified, migrated database connection.

Every service takes a Store. It is the only entry point that opens the
database, and it accepts an explicit path so callers and tests never have to
touch the user's real data.
"""

import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Self

from xoot.store.connection import connect
from xoot.store.migrator import migrate
from xoot.store.paths import default_db_path, prepare_db_file
from xoot.store.transaction import read_transaction, write_transaction


class Store(AbstractContextManager["Store"]):
    """
    Owns one SQLite connection and hands out read and write transactions.

    Not thread-safe: use one Store per thread or process.
    """

    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        """
        Wrap an already verified and migrated connection. Use Store.open.

        Args:
            - conn (sqlite3.Connection): the connection.
            - path (Path): the database file it points at.
        """
        self._conn = conn
        self.path = path

    @classmethod
    def open(cls, path: Path | None = None) -> Self:
        """
        Open (creating if needed) and migrate the database.

        Args:
            - path (Path | None): database file; the XDG default when None.

        Returns:
            - store (Store): a ready store.

        Raises:
            - PragmaCheckError: the connection could not be made safe.
            - SchemaVersionError: the database is newer than this code.
            - OSError: the directory or file could not be created.
        """
        db_path = default_db_path() if path is None else path
        prepare_db_file(db_path)
        conn = connect(db_path)
        try:
            migrate(conn)
        except BaseException:
            conn.close()
            raise
        return cls(conn, db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        """The underlying connection, for read-only inspection."""
        return self._conn

    def write(self) -> AbstractContextManager[sqlite3.Connection]:
        """
        Open a BEGIN IMMEDIATE transaction (commit on success, else rollback).

        Returns:
            - scope (AbstractContextManager[sqlite3.Connection]): yields the
              connection.
        """
        return write_transaction(self._conn)

    def read(self) -> AbstractContextManager[sqlite3.Connection]:
        """
        Open a read-only snapshot in which any write fails.

        Returns:
            - scope (AbstractContextManager[sqlite3.Connection]): yields the
              connection.
        """
        return read_transaction(self._conn)

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the store when leaving a with-block."""
        self.close()
