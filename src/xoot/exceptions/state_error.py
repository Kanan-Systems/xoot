"""Raised when an item state breaks the project's active workflow."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class StateError(RuleViolationError):
    """
    The state is not in the active workflow, or the transition is not
    allowed.
    """
