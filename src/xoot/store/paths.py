"""
Database location and file creation.

Resolves the default XDG path and creates the directory and file with
owner-only permissions. The tracker data is private to the user.
"""

import os
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600


def default_db_path() -> Path:
    """
    Return the default database path.

    Uses $XDG_DATA_HOME/xoot/xoot.db; per the XDG spec a relative or empty
    value is ignored and ~/.local/share is used instead.

    Returns:
        - path (Path): the default database file path.
    """
    base = os.environ.get("XDG_DATA_HOME", "")
    root = Path(base) if os.path.isabs(base) else Path.home() / ".local" / "share"
    return root / "xoot" / "xoot.db"


def db_path_from_arg(value: str | None) -> Path:
    """
    Turn a --db option into the database path both entry points use.

    Uses abspath, not resolve(): following a symlink here would hide it from
    the store's symlink refusal.

    Args:
        - value (str | None): the option as given, "~" allowed; None for
          the default.

    Returns:
        - path (Path): an absolute path, or default_db_path() for None.
    """
    if value is None:
        return default_db_path()
    return Path(os.path.abspath(os.path.expanduser(value)))


def prepare_db_file(path: Path) -> None:
    """
    Create the database directory and file if they do not exist yet.

    Only what this call creates gets the restrictive modes: an existing
    directory the caller chose is never chmod-ed. Modes are set explicitly
    after creation so the process umask cannot widen them. Concurrent
    callers are safe: whoever loses the creation race uses the winner's file.

    Args:
        - path (Path): the database file path.

    Raises:
        - OSError: the directory or file could not be created.
    """
    directory = path.parent
    try:
        directory.mkdir(mode=DIR_MODE, parents=True)
    except FileExistsError:
        pass
    else:
        directory.chmod(DIR_MODE)
    try:
        # O_EXCL also refuses to follow a symlink planted at the path.
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, FILE_MODE
        )
    except FileExistsError:
        return
    try:
        os.fchmod(fd, FILE_MODE)
    finally:
        os.close(fd)
