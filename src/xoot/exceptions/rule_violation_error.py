"""Base error for writes rejected by a domain rule."""

from xoot.exceptions.xoot_error import XootError


class RuleViolationError(XootError):
    """A write would break a domain rule; nothing was written."""
