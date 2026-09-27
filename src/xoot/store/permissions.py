"""
Refusing database files another account could read or redirect.

The tracker data is private to one user. Before a store opens, the data
directory, the database and any WAL/SHM file are lstat-ed; a symlink, a
foreign owner or any group/other permission bit makes the open fail. Modes
are reported, never repaired.
"""

import os
import stat
from pathlib import Path

from xoot.exceptions.unsafe_path_error import UnsafePathError

SIDECAR_SUFFIXES = ("-wal", "-shm")
_GROUP_OR_OTHER = 0o077


def check_private_files(db_path: Path, *, must_exist: bool) -> None:
    """
    Check the data directory, the database and its WAL/SHM files.

    WAL/SHM files are checked only when present. The directory and the
    database are skipped when absent unless must_exist is set.

    Args:
        - db_path (Path): the database file path.
        - must_exist (bool): whether the directory and database must exist.

    Raises:
        - UnsafePathError: a path is a symlink, not owned by the current
          user, or has a group or other permission bit set.
        - FileNotFoundError: must_exist is set and the directory or the
          database is missing.
    """
    _check(db_path.parent, must_exist)
    _check(db_path, must_exist)
    for suffix in SIDECAR_SUFFIXES:
        _check(db_path.with_name(db_path.name + suffix), False)


def _check(path: Path, must_exist: bool) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if must_exist:
            raise
        return
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        raise UnsafePathError(path, mode, "is a symlink")
    uid = os.getuid()
    if info.st_uid != uid:
        raise UnsafePathError(path, mode, f"is owned by uid {info.st_uid}, not {uid}")
    if mode & _GROUP_OR_OTHER:
        raise UnsafePathError(path, mode, "grants group or other permissions")
