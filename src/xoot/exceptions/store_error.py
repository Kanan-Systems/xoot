"""Base error for storage failures: opening, verifying or migrating the DB."""

from xoot.exceptions.xoot_error import XootError


class StoreError(XootError):
    """The database could not be opened or brought to a usable state."""
