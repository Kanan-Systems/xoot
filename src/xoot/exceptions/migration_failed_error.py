"""Raised when SQLite fails while bringing the schema up to date."""

import sqlite3

from xoot.exceptions.store_error import StoreError


class MigrationFailedError(StoreError):
    """
    Reading the schema version, or applying one migration, failed; that
    migration's transaction was rolled back.

    The message names the target version and SQLite's error code name only;
    the driver's own text quotes the failing SQL, so it is kept on
    __cause__.
    """

    def __init__(self, version: int | None, error: sqlite3.Error) -> None:
        """
        Record which migration failed and how.

        Args:
            - version (int | None): the version being applied, or None when
              the failure came from reading the current version.
            - error (sqlite3.Error): the driver's error.
        """
        # Errors raised by the driver itself (e.g. a closed connection) carry
        # no SQLite error name.
        errorname = getattr(error, "sqlite_errorname", None)
        name = errorname or type(error).__name__
        step = (
            "reading the schema version"
            if version is None
            else f"migrating to schema version {version}"
        )
        super().__init__(f"{step} failed ({name})")
        self.version = version
        self.sqlite_errorname = errorname
