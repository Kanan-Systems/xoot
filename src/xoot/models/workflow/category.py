"""Workflow categories: the fixed meanings every project state maps onto."""

from enum import StrEnum


class Category(StrEnum):
    """
    The fixed set of categories. Project workflows name their own states,
    but every state belongs to exactly one of these, and domain rules
    (backlogs, session close, tree filtering) reason only in categories.
    """

    OPEN = "open"
    ACTIVE = "active"
    BLOCKED = "blocked"
    AWAITING_INPUT = "awaiting_input"
    DONE = "done"
    DROPPED = "dropped"
    BACKLOGGED = "backlogged"


TERMINAL_CATEGORIES = frozenset({Category.DONE, Category.DROPPED})
