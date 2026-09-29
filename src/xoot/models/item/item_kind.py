"""Item kinds: the three work levels plus backlog entries."""

from enum import StrEnum


class ItemKind(StrEnum):
    """
    A goal holds batches, a batch holds subtasks. A backlog item is open work
    found along the way; it sits on a batch, a goal or the project.
    """

    GOAL = "goal"
    BATCH = "batch"
    SUBTASK = "subtask"
    BACKLOG = "backlog"


WORK_KINDS = frozenset({ItemKind.GOAL, ItemKind.BATCH, ItemKind.SUBTASK})
"""The kinds that own decisions and that bulk create and item_create make."""
