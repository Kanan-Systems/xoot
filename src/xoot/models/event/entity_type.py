"""Entity types an event can describe."""

from enum import StrEnum


class EntityType(StrEnum):
    """
    Project aliases and paths have no id of their own; their events are
    recorded on the owning project.
    """

    PROJECT = "project"
    WORKFLOW = "workflow"
    ITEM = "item"
    DECISION = "decision"
