"""Raised when a paste is refused before or while its block runs."""

from xoot.exceptions.xoot_error import XootError


class PasteError(XootError):
    """
    The paste cannot be applied: the input is too large or not UTF-8, the
    block is missing, repeated or invalid, or the plan changed since the
    preview. Nothing was written.

    The message is fixed text plus keys, refs and op numbers only; it never
    quotes other input.
    """
