"""Raised when a capture, cover or push breaks a backlog rule."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class BacklogError(RuleViolationError):
    """
    The backlog operation is not allowed where the item sits: a project-level
    item cannot be covered or pushed, a goal-level item needs a named batch,
    a closed item cannot move. Nothing was written.

    The message is fixed text plus stored keys only, so it is safe to show.
    """
