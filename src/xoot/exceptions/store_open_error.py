"""Raised when SQLite cannot open or configure the database file."""

import sqlite3
from pathlib import Path

from xoot.exceptions.store_error import StoreError


class StoreOpenError(StoreError):
    """
    The database at a path could not be opened or have its pragmas set: it
    is not a SQLite file, is unreadable, or stayed locked past the busy
    timeout.

    The message names the path and SQLite's error code name only; the
    driver's own text can quote SQL, so it is kept on __cause__.
    """

    def __init__(self, path: Path, error: sqlite3.Error) -> None:
        """
        Record the path and the driver's error code name.

        Args:
            - path (Path): the database file.
            - error (sqlite3.Error): the driver's error.
        """
        # Errors raised by the driver itself (e.g. a closed connection) carry
        # no SQLite error name.
        errorname = getattr(error, "sqlite_errorname", None)
        name = errorname or type(error).__name__
        super().__init__(f"could not open the database at {path} ({name})")
        self.path = path
        self.sqlite_errorname = errorname
