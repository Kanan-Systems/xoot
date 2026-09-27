"""Raised when a database operation fails for a reason other than a constraint."""

import sqlite3

from xoot.exceptions.store_error import StoreError


class DatabaseAccessError(StoreError):
    """
    SQLite could not run a statement: the lock was not obtained within the
    busy timeout, the store was closed, or the file is unreadable. The
    sqlite3 error is chained as __cause__.
    """

    def __init__(self, error: sqlite3.Error) -> None:
        """
        Keep the driver's error name for the caller.

        Args:
            - error (sqlite3.Error): the driver's error.
        """
        super().__init__(f"database operation failed: {error}")
        self.sqlite_errorname = getattr(error, "sqlite_errorname", None)
