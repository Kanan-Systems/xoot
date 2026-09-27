"""
Shared field types and helpers for every model.

Holds the input limits in one place so stored rows and service inputs enforce
identical rules, and defines the single timestamp text format used in storage.
"""

import posixpath
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    PlainSerializer,
    StrictInt,
    StringConstraints,
)

TITLE_MAX = 200
BODY_MAX = 32768
PATH_MAX = 4096
SQLITE_INT_MAX = 2**63 - 1


def reject_nul(value: str) -> str:
    """
    Reject strings containing NUL characters.

    SQLite text functions stop at NUL, so a NUL could hide content from
    length checks and from anyone reading the data back.

    Args:
        - value (str): the candidate string.

    Returns:
        - value (str): the same string, unchanged.

    Raises:
        - ValueError: the string contains a NUL character.
    """
    if "\x00" in value:
        raise ValueError("NUL characters are not allowed")
    return value


def normalize_absolute_path(value: str) -> str:
    """
    Normalize an absolute POSIX path lexically.

    Paths are only compared as strings, never opened, so lexical
    normalization is enough and keeps xoot away from the filesystem.

    Args:
        - value (str): an absolute path.

    Returns:
        - path (str): the path without redundant separators or dot segments.

    Raises:
        - ValueError: the path is not absolute.
    """
    if not value.startswith("/"):
        raise ValueError("path must be absolute")
    # normpath keeps a leading "//" (POSIX allows it); collapse it so one
    # directory has exactly one spelling.
    return "/" + posixpath.normpath(value).lstrip("/")


def format_timestamp(value: datetime) -> str:
    """
    Render a datetime in the fixed-width UTC storage format.

    One width for every row keeps text comparison chronological in SQL.

    Args:
        - value (datetime): a timezone-aware datetime.

    Returns:
        - text (str): e.g. "2026-09-26T18:00:00.000000Z".
    """
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def provided_fields(model: BaseModel) -> dict[str, Any]:
    """
    Return only the fields a caller explicitly set on a partial update.

    Lets partial updates tell "leave unchanged" apart from "set to None".

    Args:
        - model (BaseModel): the update model.

    Returns:
        - fields (dict[str, Any]): field name to value, explicitly set only.
    """
    return {name: getattr(model, name) for name in sorted(model.model_fields_set)}


def reject_explicit_none(model: BaseModel, names: tuple[str, ...]) -> None:
    """
    Reject an explicit None for fields that cannot be cleared.

    Args:
        - model (BaseModel): the update model.
        - names (tuple[str, ...]): fields that must not be set to None.

    Raises:
        - ValueError: one of the fields was explicitly set to None.
    """
    for name in names:
        if name in model.model_fields_set and getattr(model, name) is None:
            raise ValueError(f"{name} cannot be cleared")


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Strict: every id, number and version is a real int. Lax mode would accept
# "5" or True, and SQLite would then match them to a stored row.
Id = Annotated[StrictInt, Field(ge=1, le=SQLITE_INT_MAX)]
Title = Annotated[
    str,
    StringConstraints(min_length=1, max_length=TITLE_MAX),
    AfterValidator(reject_nul),
]
Body = Annotated[
    str, StringConstraints(max_length=BODY_MAX), AfterValidator(reject_nul)
]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,31}$")]
StateName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]
AbsolutePath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=PATH_MAX),
    AfterValidator(reject_nul),
    AfterValidator(normalize_absolute_path),
]
Timestamp = Annotated[
    AwareDatetime,
    AfterValidator(_as_utc),
    PlainSerializer(format_timestamp, return_type=str, when_used="json"),
]
