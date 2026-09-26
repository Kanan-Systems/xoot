"""Raised when an item state breaks the project's active workflow."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class StateError(RuleViolationError):
    """
    The state is unknown, the transition is not allowed, or
    backlog_session_id is set outside the backlogged category.
    """
