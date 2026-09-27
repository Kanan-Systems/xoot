"""Raised when the database rejects a write on one of its constraints."""

import sqlite3

from xoot.exceptions.store_error import StoreError


class IntegrityViolationError(StoreError):
    """
    A CHECK, UNIQUE, foreign key or trigger refused a write; the transaction
    was rolled back.

    Services validate first, so reaching the schema's own guard means a
    check was missed or bypassed. The sqlite3.IntegrityError is chained as
    __cause__.
    """

    def __init__(self, error: sqlite3.IntegrityError) -> None:
        """
        Keep the constraint that fired.

        Args:
            - error (sqlite3.IntegrityError): the driver's error.
        """
        super().__init__(f"database constraint refused the write: {error}")
        self.sqlite_errorname = error.sqlite_errorname
