"""Raised when key qualifiers disagree with each other or with the project."""

from xoot.exceptions.xoot_error import XootError


class QualifierError(XootError):
    """
    Two keys of one call are qualified with different project prefixes, a
    qualifier is not a well-formed prefix, or a qualifier names another
    project than the explicit project argument.

    The message is fixed text plus well-formed prefixes only.
    """
