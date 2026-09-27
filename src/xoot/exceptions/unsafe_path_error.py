"""Raised when a database path could be read or redirected by someone else."""

from pathlib import Path

from xoot.exceptions.store_error import StoreError


class UnsafePathError(StoreError):
    """
    The data directory, the database or a WAL/SHM file is a symlink, is not
    owned by the current user, or has a group or other permission bit set.

    The store refuses to open instead of repairing: it never runs chmod.
    """

    def __init__(self, path: Path, mode: int, reason: str) -> None:
        """
        Record the offending path and its mode.

        Args:
            - path (Path): the path that failed the check.
            - mode (int): its permission bits, as lstat reported them.
            - reason (str): what is wrong, e.g. "is a symlink".
        """
        super().__init__(f"refusing to open {path}: it {reason} (mode {mode:04o})")
        self.path = path
        self.mode = mode
