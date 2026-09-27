"""Raised when a confirm token cannot authorize the write it is presented for."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class ConfirmTokenError(RuleViolationError):
    """
    The token is unknown, expired or already used, or was issued for another
    tool, session or set of arguments. Nothing was written.

    The message is one of a fixed set of reasons and never contains the token.
    """
