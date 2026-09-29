"""Raised when the database was written by xoot 0.2 or earlier."""

from xoot.exceptions.store_error import StoreError

LEGACY_MESSAGE = (
    "this database was created by xoot 0.2 or earlier; the data model changed "
    "and it cannot be upgraded. Move the file aside, then run `xoot init` again"
)


class LegacyDatabaseError(StoreError):
    """
    The database holds the 0.2 schema: schema version 1, or a session table.

    Nothing is migrated and the file is never written: the store refuses it
    before any pragma or migration runs, so the file stays byte-identical.
    """

    def __init__(self) -> None:
        """Build the fixed message; it names no path and no content."""
        super().__init__(LEGACY_MESSAGE)
