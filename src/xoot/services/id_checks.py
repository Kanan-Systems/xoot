"""
Guards for the raw id and version arguments of service entry points.

Services bind these straight into SQL, where SQLite's type affinity would
turn "5", "05", "5.0" or True into a valid-looking id. Every entry point
checks them before any statement runs, so a wrong type can never select or
write a row.
"""

from xoot.exceptions.invalid_id_error import InvalidIdError
from xoot.models.fields import SQLITE_INT_MAX


def check_id(name: str, value: object) -> int:
    """
    Accept only an int (not a bool) in the range SQLite stores for ids.

    Args:
        - name (str): the argument name, used in the error.
        - value (object): the raw argument.

    Returns:
        - value (int): the same value, typed.

    Raises:
        - InvalidIdError: the value is not an int, is a bool, or is out of
          range.
    """
    # bool is an int subclass, so it has to be excluded explicitly.
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= SQLITE_INT_MAX
    ):
        raise InvalidIdError(name, value)
    return value


def check_optional_id(name: str, value: object) -> int | None:
    """
    Like check_id, but None is allowed and returned as is.

    Args:
        - name (str): the argument name, used in the error.
        - value (object): the raw argument.

    Returns:
        - value (int | None): the same value, typed.

    Raises:
        - InvalidIdError: the value is neither None nor a valid id.
    """
    return None if value is None else check_id(name, value)
