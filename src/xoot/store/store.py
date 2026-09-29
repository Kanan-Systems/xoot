"""
The Store: one open, verified, migrated database connection.

Every service takes a Store. It is the only entry point that opens the
database, and it accepts an explicit path so callers and tests never have to
touch the user's real data. Its transaction scopes re-raise every sqlite3
error as an XootError, so no raw driver exception escapes a service.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from pathlib import Path
from types import TracebackType
from typing import Self

from xoot.exceptions.database_access_error import DatabaseAccessError
from xoot.exceptions.database_busy_error import DatabaseBusyError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.legacy_database_error import LegacyDatabaseError
from xoot.exceptions.store_open_error import StoreOpenError
from xoot.store.connection import connect
from xoot.store.migrator import is_legacy, migrate
from xoot.store.paths import default_db_path, prepare_db_file
from xoot.store.permissions import check_private_files
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
            - UnsafePathError: the directory, the database or a WAL/SHM file
              is a symlink, owned by another user, or group/other accessible.
            - PragmaCheckError: the connection could not be made safe.
            - StoreOpenError: SQLite could not open or configure the file.
            - LegacyDatabaseError: the file holds the xoot 0.2 schema; it
              is left byte-identical.
            - SchemaVersionError: the database is newer than this code.
            - MigrationFailedError: SQLite failed while migrating.
            - OSError: the directory or file could not be created, or the
              pre-migration backup could not be written.
        """
        db_path = default_db_path() if path is None else path
        # Checked before creating anything, so nothing is written through a
        # planted symlink, and again after, to cover what was just created.
        check_private_files(db_path, must_exist=False)
        prepare_db_file(db_path)
        check_private_files(db_path, must_exist=True)
        _refuse_legacy(db_path)
        try:
            conn = connect(db_path)
        except sqlite3.Error as exc:
            raise StoreOpenError(db_path, exc) from exc
        try:
            migrate(conn, db_path=db_path)
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

        Raises:
            - IntegrityViolationError: a constraint refused a write.
            - DatabaseAccessError: any other sqlite3 error.
        """
        return _translated(write_transaction(self._conn))

    def read(self) -> AbstractContextManager[sqlite3.Connection]:
        """
        Open a read-only snapshot in which any write fails.

        Returns:
            - scope (AbstractContextManager[sqlite3.Connection]): yields the
              connection.

        Raises:
            - DatabaseAccessError: a sqlite3 error, including a write attempt.
        """
        return _translated(read_transaction(self._conn))

    def checkpoint(self) -> bool:
        """
        Copy the WAL into the database file and truncate the WAL.

        Waits up to the busy timeout for other connections to finish.

        Returns:
            - complete (bool): False when another connection still kept the
              checkpoint from finishing.

        Raises:
            - DatabaseAccessError: the checkpoint could not run.
        """
        with _translated(nullcontext(self._conn)) as conn:
            busy = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
        return busy == 0

    def vacuum(self) -> bool:
        """
        Rebuild the database file without free pages.

        A checkpoint first moves the WAL into the file; VACUUM then runs
        outside any transaction (SQLite refuses it inside one), and a final
        TRUNCATE checkpoint empties the WAL the rebuild went through.

        Returns:
            - complete (bool): False when another connection kept the final
              checkpoint from truncating the WAL; the rebuild is committed.

        Raises:
            - DatabaseBusyError: another connection kept the first
              checkpoint or the VACUUM from running.
            - DatabaseAccessError: any other sqlite3 error.
        """
        if not self.checkpoint():
            raise DatabaseBusyError()
        try:
            with _translated(nullcontext(self._conn)) as conn:
                conn.execute("VACUUM")
        except DatabaseAccessError as exc:
            if _is_busy(exc.__cause__):
                raise DatabaseBusyError() from exc
            raise
        return self.checkpoint()

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


def is_legacy_file(db_path: Path) -> bool:
    """
    Tell whether a database file holds the xoot 0.2 schema, without writing.

    connect() switches the journal mode, which rewrites the header of a
    file not in WAL mode; this plain connection only reads, so the file
    stays byte-identical.

    Args:
        - db_path (Path): an existing database file.

    Returns:
        - legacy (bool): True for a 0.2 database.

    Raises:
        - StoreOpenError: SQLite could not open or read the file.
    """
    try:
        probe = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise StoreOpenError(db_path, exc) from exc
    try:
        return is_legacy(probe)
    except sqlite3.Error as exc:
        raise StoreOpenError(db_path, exc) from exc
    finally:
        probe.close()


def _refuse_legacy(db_path: Path) -> None:
    """Refuse a 0.2 database before any pragma can write to it."""
    if is_legacy_file(db_path):
        raise LegacyDatabaseError()


@contextmanager
def _translated(
    scope: AbstractContextManager[sqlite3.Connection],
) -> Iterator[sqlite3.Connection]:
    """Run a scope, re-raising its sqlite3 errors as XootErrors (chained)."""
    try:
        with scope as conn:
            yield conn
    except sqlite3.IntegrityError as exc:
        raise IntegrityViolationError(exc) from exc
    except sqlite3.Error as exc:
        raise DatabaseAccessError(exc) from exc


def _is_busy(error: BaseException | None) -> bool:
    """Tell whether a driver error is SQLITE_BUSY or SQLITE_LOCKED."""
    code = getattr(error, "sqlite_errorcode", None)
    return code is not None and code & 0xFF in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    )
