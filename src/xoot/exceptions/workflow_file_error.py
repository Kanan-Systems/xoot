"""Raised when a workflow file cannot be read as TOML."""

from xoot.exceptions.xoot_error import XootError


class WorkflowFileError(XootError):
    """
    The workflow file is missing, not a regular file, larger than the limit,
    not UTF-8 or not TOML. Nothing was written.

    The message is one of a fixed set of reasons; it never quotes the file.
    """
