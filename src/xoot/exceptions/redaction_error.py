"""Raised when a redaction request is refused."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class RedactionError(RuleViolationError):
    """
    The redaction is not allowed: the actor is not the user, or the entity
    or field is not one that can be redacted. Nothing was written.
    """
