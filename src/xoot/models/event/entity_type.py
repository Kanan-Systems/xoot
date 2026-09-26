"""Entity types an event can describe."""

from enum import StrEnum


class EntityType(StrEnum):
    """
    Aliases, paths and session links have no id of their own; their events
    are recorded on the owning project or session.
    """

    PROJECT = "project"
    WORKFLOW = "workflow"
    ITEM = "item"
    SESSION = "session"
    DECISION = "decision"
