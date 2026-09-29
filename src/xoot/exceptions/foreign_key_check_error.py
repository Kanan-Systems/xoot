"""Raised when a migration leaves rows whose foreign keys point nowhere."""

from xoot.exceptions.store_error import StoreError


class ForeignKeyCheckError(StoreError):
    """
    PRAGMA foreign_key_check reported violations before a migration's
    commit. The migration rolls back. The message names the tables only.
    """

    def __init__(self, tables: tuple[str, ...]) -> None:
        """
        Record the tables holding violating rows.

        Args:
            - tables (tuple[str, ...]): the table names, sorted.
        """
        super().__init__(f"foreign key check failed in: {', '.join(tables)}")
        self.tables = tables
