"""Raised when neither a name nor a directory resolves to a project."""

from xoot.exceptions.xoot_error import XootError


class ProjectResolutionError(XootError):
    """
    No project has the given alias or key prefix, or no registered path
    contains the directory.

    The message lists every registered name. Those are validated slugs read
    from the database; the name the caller gave is never echoed.
    """

    def __init__(self, names: tuple[str, ...]) -> None:
        """
        Record the names the caller could have used.

        Args:
            - names (tuple[str, ...]): every key prefix and alias, sorted.
        """
        if names:
            message = f"project not resolved; one of: {', '.join(names)}"
        else:
            message = "project not resolved and no projects are registered"
        super().__init__(message)
        self.names = names
