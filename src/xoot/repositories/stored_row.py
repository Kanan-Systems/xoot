"""
Reading a stored row into its model, the one way every repository does it.

A row that does not fit its model was written by other code (a newer xoot,
or by hand), so the failure is a StoredDataError naming the table, row id,
field and value, never a pydantic ValidationError that the entry points
would report as the caller's invalid arguments. Only a short, token-like
value is echoed; anything else (a title, a body) is described, not shown.
"""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from xoot.exceptions.stored_data_error import StoredDataError

# Enum values, states, keys and numbers; never free text.
_SHOWABLE = re.compile(r"[A-Za-z0-9_.:/-]{1,64}")


def from_row[M: BaseModel](model: type[M], table: str, values: Mapping[str, Any]) -> M:
    """
    Validate a stored row as a model.

    Args:
        - model (type[M]): the model the row should fit.
        - table (str): the table the row came from, for the message.
        - values (Mapping[str, Any]): the row's columns, JSON already decoded.

    Returns:
        - record (M): the validated model.

    Raises:
        - StoredDataError: the row does not fit the model.
    """
    try:
        return model.model_validate(dict(values))
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "row"
        row_id = values.get("id")
        raise StoredDataError(
            table,
            row_id if isinstance(row_id, int) else None,
            field,
            shown_value(first.get("input")),
        ) from exc


def shown_value(value: Any) -> str:
    """
    Describe a stored value so it can be shown without leaking text.

    Args:
        - value (Any): the value pydantic refused.

    Returns:
        - shown (str): the quoted value when it is short and token-like,
          otherwise its type (and length, for text).
    """
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value)
        if _SHOWABLE.fullmatch(text):
            return repr(value)
    if isinstance(value, str):
        return f"(text of {len(value)} characters, not shown)"
    return f"(a {type(value).__name__}, not shown)"
