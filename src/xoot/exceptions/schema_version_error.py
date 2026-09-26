"""Raised when the database schema is newer than this code understands."""

from xoot.exceptions.store_error import StoreError


class SchemaVersionError(StoreError):
    """
    The database's user_version is ahead of the newest known migration.

    Opening it could silently misread or corrupt data written by a newer
    xoot, so the store refuses to open it.
    """

    def __init__(self, found: int, known: int) -> None:
        """
        Record both versions for the caller.

        Args:
            - found (int): user_version stored in the database.
            - known (int): newest migration version this code ships.
        """
        super().__init__(
            f"database schema version {found} is newer than supported {known}"
        )
        self.found = found
        self.known = known
