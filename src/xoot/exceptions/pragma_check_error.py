"""Raised when a connection's safety pragmas did not take effect."""

from xoot.exceptions.store_error import StoreError


class PragmaCheckError(StoreError):
    """
    A required pragma read back with the wrong value.

    The connection is refused (fail closed): without foreign keys or WAL the
    integrity and concurrency guarantees the services rely on do not hold.
    """
