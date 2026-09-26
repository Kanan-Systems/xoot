"""Raised when a write references an entity from another project."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class CrossProjectError(RuleViolationError):
    """A referenced parent, session, item or decision is in another project."""
