"""Raised when a write needs an open session and the session is not open."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class SessionStateError(RuleViolationError):
    """The session is closed, or a session was required and not given."""
