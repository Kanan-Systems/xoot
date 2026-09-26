"""Raised when an item's parent breaks the goal > batch > subtask hierarchy."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class HierarchyError(RuleViolationError):
    """The parent kind is not allowed for the child kind."""
