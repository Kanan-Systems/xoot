"""Raised when a unique name (key prefix, alias, path) is already taken."""

from xoot.exceptions.xoot_error import XootError


class DuplicateError(XootError):
    """A value that must be unique is already registered."""

    def __init__(self, field: str, value: str, holder: str | None = None) -> None:
        """
        Record the clashing value and, when known, what already holds it.

        Args:
            - field (str): which unique field clashed, e.g. "alias".
            - value (str): the value that is already in use.
            - holder (str | None): what the value is registered as, e.g.
              "an alias of project xoot"; None for a plain clash.
        """
        if holder is None:
            message = f"{field} {value!r} is already registered"
        else:
            message = f"{value!r} is already registered as {holder}"
        super().__init__(message)
        self.field = field
        self.value = value
