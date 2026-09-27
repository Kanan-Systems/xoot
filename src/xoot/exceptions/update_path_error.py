"""Raised when an item update mixes a path that must come alone with other fields."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class UpdatePathError(RuleViolationError):
    """
    A parent change, or a drop of an item with children, was combined with
    other fields. Nothing was written.

    The message is fixed text naming the field that must come alone.
    """
