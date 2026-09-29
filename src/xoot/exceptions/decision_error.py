"""Raised when a decision cannot be recorded or changed as asked."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class DecisionError(RuleViolationError):
    """
    The decision is superseded, its target is already superseded or on
    another goal, or its owner is not a goal, batch or subtask.

    The message is fixed text plus stored keys only, so it is safe to show.
    """
