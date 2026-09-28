"""
Forward-only schema migrations tracked by PRAGMA user_version.

Migrations are numbered .sql files shipped in store/migrations. Each runs in
its own BEGIN IMMEDIATE transaction and re-reads user_version under the lock,
so several processes opening a fresh database at once all succeed. SQLite
failures surface as MigrationFailedError, never as raw sqlite3 errors.
"""

import re
import sqlite3
from collections.abc import Iterable, Sequence
from importlib import resources

from xoot.exceptions.migration_error import MigrationError
from xoot.exceptions.migration_failed_error import MigrationFailedError
from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.store.transaction import write_transaction

MIGRATIONS_PACKAGE = "xoot.store.migrations"
_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def load_migrations() -> list[tuple[int, str]]:
    """
    Load the shipped migrations in version order.

    Returns:
        - migrations (list[tuple[int, str]]): (version, sql) pairs.

    Raises:
        - MigrationError: the shipped files are misnamed or not contiguous.
    """
    files = resources.files(MIGRATIONS_PACKAGE)
    entries = [
        (entry.name, entry.read_text(encoding="utf-8"))
        for entry in files.iterdir()
        if entry.name.endswith(".sql")
    ]
    return order_migrations(entries)


def latest_version() -> int:
    """
    The newest schema version the shipped migrations reach.

    Returns:
        - version (int): the highest migration number, 0 when none ship.

    Raises:
        - MigrationError: the shipped files are misnamed or not contiguous.
    """
    migrations = load_migrations()
    return migrations[-1][0] if migrations else 0


def order_migrations(entries: Iterable[tuple[str, str]]) -> list[tuple[int, str]]:
    """
    Validate migration file names and order them.

    Versions must run 1, 2, 3... with no gap or duplicate, so a missing file
    can never be silently skipped.

    Args:
        - entries (Iterable[tuple[str, str]]): (file name, sql) pairs.

    Returns:
        - migrations (list[tuple[int, str]]): (version, sql), ascending.

    Raises:
        - MigrationError: a name does not match NNNN_name.sql, or the
          versions are not contiguous from 1.
    """
    numbered = []
    for name, sql in entries:
        match = _NAME.match(name)
        if match is None:
            raise MigrationError(f"invalid migration file name: {name!r}")
        numbered.append((int(match.group(1)), sql))
    numbered.sort(key=lambda pair: pair[0])
    versions = [version for version, _ in numbered]
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError(f"migration versions are not contiguous: {versions}")
    return numbered


def user_version(conn: sqlite3.Connection) -> int:
    """
    Read the schema version stored in the database header.

    Args:
        - conn (sqlite3.Connection): an open connection.

    Returns:
        - version (int): the current user_version.

    Raises:
        - MigrationFailedError: SQLite could not read it.
    """
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.Error as exc:
        raise MigrationFailedError(None, exc) from exc


def migrate(
    conn: sqlite3.Connection, migrations: Sequence[tuple[int, str]] | None = None
) -> int:
    """
    Apply every pending migration, oldest first.

    Args:
        - conn (sqlite3.Connection): an autocommit connection.
        - migrations (Sequence[tuple[int, str]] | None): ordered (version,
          sql) pairs; the shipped set when None.

    Returns:
        - version (int): the schema version after migrating.

    Raises:
        - SchemaVersionError: the database is newer than the known set.
        - MigrationError: the shipped files are malformed.
        - MigrationFailedError: SQLite failed; the failing migration was
          rolled back.
    """
    ordered = load_migrations() if migrations is None else list(migrations)
    known = ordered[-1][0] if ordered else 0
    applying: int | None = None
    try:
        _refuse_newer(user_version(conn), known)
        for version, sql in ordered:
            if version <= user_version(conn):
                continue
            applying = version
            with write_transaction(conn):
                # Another process may have migrated while we waited for the lock.
                current = user_version(conn)
                _refuse_newer(current, known)
                if current >= version:
                    continue
                conn.executescript(sql)
                # PRAGMA takes no bound parameters; version is an int we parsed.
                conn.execute(f"PRAGMA user_version = {int(version)}")
            applying = None
        return user_version(conn)
    except sqlite3.Error as exc:
        raise MigrationFailedError(applying, exc) from exc


def _refuse_newer(found: int, known: int) -> None:
    if found > known:
        raise SchemaVersionError(found, known)
