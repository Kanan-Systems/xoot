"""Raised when a service is given an id or version that is not a plain int."""

from xoot.exceptions.xoot_error import XootError
from xoot.models.fields import SQLITE_INT_MAX


class InvalidIdError(XootError):
    """
    An id or version argument is not an int in the stored range.

    SQLite's type affinity would quietly turn "5", "5.0" or True into a
    matching id, so these are refused before any SQL runs. The message
    names the argument and the type, not the value.
    """

    def __init__(self, name: str, value: object) -> None:
        """
        Record which argument was wrong and what type it had.

        Args:
            - name (str): the argument name, e.g. "item_id".
            - value (object): the rejected value.
        """
        super().__init__(
            f"{name} must be an int from 1 to {SQLITE_INT_MAX}, "
            f"got {type(value).__name__}"
        )
        self.name = name
        self.type_name = type(value).__name__
