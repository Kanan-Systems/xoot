"""Item kinds: the three levels of the item hierarchy."""

from enum import StrEnum


class ItemKind(StrEnum):
    """A goal holds batches, a batch holds subtasks; subtasks may be unfiled."""

    GOAL = "goal"
    BATCH = "batch"
    SUBTASK = "subtask"
