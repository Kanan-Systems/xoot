"""
The copy taken before an existing database is migrated.

The copy goes through SQLite's online backup API, so it is consistent even
with WAL content not yet checkpointed. It is written next to the database as
<name>.pre-v<target> with owner-only permissions, created exclusively so a
planted symlink is never followed, and only the newest such copy is kept.
"""

import os
import re
import sqlite3
from pathlib import Path

from xoot.store.paths import FILE_MODE

_SUFFIX = re.compile(r"\.pre-v[0-9]+")


def backup_path(db_path: Path, target: int) -> Path:
    """
    Name the backup taken before migrating to a schema version.

    Args:
        - db_path (Path): the database file.
        - target (int): the schema version being migrated to.

    Returns:
        - path (Path): <db_path>.pre-v<target>.
    """
    return db_path.with_name(f"{db_path.name}.pre-v{target}")


def backup_database(conn: sqlite3.Connection, db_path: Path, target: int) -> Path:
    """
    Copy the database before a migration, keeping only this newest copy.

    Older <name>.pre-v* copies are removed first, then the new one is
    created with O_EXCL and mode 0600 and filled by the backup API.

    Args:
        - conn (sqlite3.Connection): an open connection to the database.
        - db_path (Path): the database file.
        - target (int): the schema version being migrated to.

    Returns:
        - path (Path): the backup file.

    Raises:
        - OSError: the file could not be created or an old copy removed.
        - sqlite3.Error: the backup API failed.
    """
    for old in _previous_backups(db_path):
        old.unlink()
    path = backup_path(db_path, target)
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        FILE_MODE,
    )
    try:
        os.fchmod(fd, FILE_MODE)
    finally:
        os.close(fd)
    target_conn = sqlite3.connect(path)
    try:
        conn.backup(target_conn)
    finally:
        target_conn.close()
    return path


def _previous_backups(db_path: Path) -> list[Path]:
    """Every <name>.pre-v<N> next to the database, symlinks included."""
    prefix = f"{db_path.name}.pre-v"
    return sorted(
        entry
        for entry in db_path.parent.iterdir()
        if entry.name.startswith(prefix)
        and _SUFFIX.fullmatch(entry.name[len(db_path.name) :]) is not None
    )
