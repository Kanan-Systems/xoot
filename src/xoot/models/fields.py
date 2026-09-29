"""
Shared field types and helpers for every model.

Holds the input limits in one place so stored rows and service inputs enforce
identical rules, and defines the single timestamp text format used in storage.
"""

import posixpath
import re
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
from pydantic_core import PydanticCustomError

TITLE_MAX = 200
BODY_MAX = 32768
PATH_MAX = 4096
SQLITE_INT_MAX = 2**63 - 1
# A key segment: an item or decision kind, a dash and a number. The
# schema's project_alias CHECK refuses the same shapes.
_KEY_SHAPED = re.compile(r"^(goal|batch|subtask|backlog|decision)-[0-9]")
_KEY_PREFIX = re.compile(r"^[a-z][a-z0-9]{1,31}$")


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


def check_key_prefix(value: str) -> str:
    """
    Accept a key prefix, or refuse it with the rule spelled out.

    Args:
        - value (str): the candidate prefix.

    Returns:
        - value (str): the same prefix, unchanged.

    Raises:
        - PydanticCustomError: the prefix breaks the rule.
    """
    if _KEY_PREFIX.fullmatch(value) is None:
        raise PydanticCustomError(
            "key_prefix",
            "a key prefix is 2–32 lowercase letters or digits, starting with "
            "a letter; no dashes",
        )
    return value


def reject_key_shaped(value: str) -> str:
    """
    Reject an alias that looks like an item or decision key.

    A key-shaped alias would read as a record key to anyone scanning a list
    of names, even though resolution never confuses the two.

    Args:
        - value (str): a slug.

    Returns:
        - value (str): the same slug, unchanged.

    Raises:
        - PydanticCustomError: the slug is key-shaped, e.g. "goal-12".
    """
    if _KEY_SHAPED.match(value):
        raise PydanticCustomError(
            "key_shaped_alias",
            "an alias must not look like an item or decision key (a kind, a "
            "dash, then a number, such as goal-12, backlog-3 or decision-1)",
        )
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


def reject_root(value: str) -> str:
    """
    Reject the filesystem root as a project directory.

    Runs after normalization, so "/..", "//" and "/." are refused too. A
    project at "/" would claim every directory on the machine.

    Args:
        - value (str): a normalized absolute path.

    Returns:
        - value (str): the same path, unchanged.

    Raises:
        - ValueError: the path is "/".
    """
    if value == "/":
        raise ValueError("a project directory cannot be the root directory")
    return value


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
# A new alias. Stored aliases stay Slug, so a row written before this rule
# still reads back and can be removed.
Alias = Annotated[Slug, AfterValidator(reject_key_shaped)]
# No dash, unlike an alias: a prefix qualifies keys as "<prefix>:<key>"
# and stays one plain word.
KeyPrefix = Annotated[str, AfterValidator(check_key_prefix)]
StateName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z_]{0,63}$")]
AbsolutePath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=PATH_MAX),
    AfterValidator(reject_nul),
    AfterValidator(normalize_absolute_path),
]
# A directory a project may claim: any absolute path except "/".
ProjectDir = Annotated[AbsolutePath, AfterValidator(reject_root)]
Timestamp = Annotated[
    AwareDatetime,
    AfterValidator(_as_utc),
    PlainSerializer(format_timestamp, return_type=str, when_used="json"),
]
