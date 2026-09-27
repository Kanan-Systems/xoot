"""Actions an event can record."""

from enum import StrEnum


class EventAction(StrEnum):
    """The kind of mutation an event row describes."""

    CREATE = "create"
    UPDATE = "update"
    LINK = "link"
    DISPOSE = "dispose"
    CLOSE = "close"
    ADD_ALIAS = "add_alias"
    ADD_PATH = "add_path"
    REMOVE_ALIAS = "remove_alias"
    REMOVE_PATH = "remove_path"
    REDACT = "redact"
