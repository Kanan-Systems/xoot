"""Workflow categories: the fixed meanings every project state maps onto."""

from enum import StrEnum


class Category(StrEnum):
    """
    The fixed set of categories. Project workflows name their own states,
    but every state belongs to exactly one of these, and domain rules
    (completion, backlog counts, tree filtering) reason only in categories.
    Backlog is an item kind, not a category.
    """

    OPEN = "open"
    ACTIVE = "active"
    BLOCKED = "blocked"
    AWAITING_INPUT = "awaiting_input"
    DONE = "done"
    DROPPED = "dropped"


TERMINAL_CATEGORIES = frozenset({Category.DONE, Category.DROPPED})
