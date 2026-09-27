"""Raised when the user did not confirm a destructive CLI command."""

from xoot.exceptions.xoot_error import XootError


class ConfirmationError(XootError):
    """
    The command needed a yes and did not get one: stdin is not a terminal
    and --yes was not given, or the answer was not y/yes. Nothing was
    written.

    The message is one of a fixed set of reasons.
    """
