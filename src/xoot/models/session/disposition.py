"""What happens to a linked item when its session closes."""

from enum import StrEnum


class Disposition(StrEnum):
    """
    carry_over keeps the state; session_backlog and project_backlog move the
    item to the default backlogged state (with or without this session);
    dropped moves it to the default dropped state.
    """

    CARRY_OVER = "carry_over"
    SESSION_BACKLOG = "session_backlog"
    PROJECT_BACKLOG = "project_backlog"
    DROPPED = "dropped"
