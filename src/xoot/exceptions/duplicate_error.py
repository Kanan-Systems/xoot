"""Raised when a unique name (key prefix, alias, path) is already taken."""

from xoot.exceptions.xoot_error import XootError


class DuplicateError(XootError):
    """A value that must be unique is already registered."""

    def __init__(self, field: str, value: str) -> None:
        """
        Record the clashing value.

        Args:
            - field (str): which unique field clashed, e.g. "alias".
            - value (str): the value that is already in use.
        """
        super().__init__(f"{field} {value!r} is already registered")
        self.field = field
        self.value = value
