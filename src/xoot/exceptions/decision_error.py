"""Raised when a decision status change is not allowed."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class DecisionError(RuleViolationError):
    """The decision is superseded, or cannot be superseded again."""
