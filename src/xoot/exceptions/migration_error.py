"""Raised when the shipped migration files are malformed."""

from xoot.exceptions.store_error import StoreError


class MigrationError(StoreError):
    """The migration set is not a contiguous, well-named sequence."""
