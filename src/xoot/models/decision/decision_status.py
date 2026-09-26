"""Decision status."""

from enum import StrEnum


class DecisionStatus(StrEnum):
    """Superseded is terminal and only reached by a newer decision."""

    LOCKED = "locked"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"
