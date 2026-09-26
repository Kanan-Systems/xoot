"""Raised when a version-guarded UPDATE matched no row."""

from xoot.exceptions.store_error import StoreError


class StaleWriteError(StoreError):
    """
    A row changed inside what should have been an exclusive transaction.

    Services check versions under the write lock first, so this signals a
    bug rather than a user conflict; the transaction is rolled back.
    """
