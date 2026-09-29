"""
Forward-only schema migrations tracked by PRAGMA user_version.

Migrations are numbered .sql files shipped in store/migrations, starting at
the 0.3 baseline (version 2). A database at version 1, or holding the 0.2
session table, is refused: the data model changed and nothing is migrated.
Each migration runs in its own BEGIN IMMEDIATE transaction, re-reads
user_version under the lock (so several processes opening a fresh database
at once all succeed) and passes a foreign-key check before it commits.
Before an existing database takes a pending migration it is backed up.
SQLite failures surface as MigrationFailedError, never as raw sqlite3 errors.
"""

import re
import sqlite3
from collections.abc import Iterable, Sequence
from importlib import resources
from pathlib import Path

from xoot.exceptions.foreign_key_check_error import ForeignKeyCheckError
from xoot.exceptions.legacy_database_error import LegacyDatabaseError
from xoot.exceptions.migration_error import MigrationError
from xoot.exceptions.migration_failed_error import MigrationFailedError
from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.store.backup import backup_database
from xoot.store.transaction import write_transaction

MIGRATIONS_PACKAGE = "xoot.store.migrations"
# The first version the shipped set holds; version 1 was xoot 0.2's schema.
BASELINE_VERSION = 2
LEGACY_TABLE = "session"
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


def order_migrations(
    entries: Iterable[tuple[str, str]], first: int = BASELINE_VERSION
) -> list[tuple[int, str]]:
    """
    Validate migration file names and order them.

    Versions must run first, first + 1, ... with no gap or duplicate, so a
    missing file can never be silently skipped.

    Args:
        - entries (Iterable[tuple[str, str]]): (file name, sql) pairs.
        - first (int): the version the set must start at.

    Returns:
        - migrations (list[tuple[int, str]]): (version, sql), ascending.

    Raises:
        - MigrationError: a name does not match NNNN_name.sql, or the
          versions are not contiguous from first.
    """
    numbered = []
    for name, sql in entries:
        match = _NAME.match(name)
        if match is None:
            raise MigrationError(f"invalid migration file name: {name!r}")
        numbered.append((int(match.group(1)), sql))
    numbered.sort(key=lambda pair: pair[0])
    versions = [version for version, _ in numbered]
    if versions != list(range(first, first + len(versions))):
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


def is_legacy(conn: sqlite3.Connection) -> bool:
    """
    Tell whether a database holds the xoot 0.2 schema.

    Only reads: the schema version and the table list.

    Args:
        - conn (sqlite3.Connection): an open connection.

    Returns:
        - legacy (bool): True at a version from 1 up to the baseline, or
          when a session table exists.

    Raises:
        - sqlite3.Error: the database could not be read.
    """
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if 0 < version < BASELINE_VERSION:
        return True
    row = conn.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = ?",
        (LEGACY_TABLE,),
    ).fetchone()
    return row is not None


def check_foreign_keys(conn: sqlite3.Connection) -> None:
    """
    Refuse to commit while any row breaks a foreign key.

    Foreign keys stay on during migrations; a migration that rebuilds a
    table still has to prove, before its commit, that every reference
    resolves. This runs inside the migration's transaction.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.

    Raises:
        - ForeignKeyCheckError: violations were found; the message names
          the tables only.
    """
    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    if rows:
        raise ForeignKeyCheckError(tuple(sorted({str(row[0]) for row in rows})))


def migrate(
    conn: sqlite3.Connection,
    migrations: Sequence[tuple[int, str]] | None = None,
    *,
    db_path: Path | None = None,
) -> int:
    """
    Apply every pending migration, oldest first.

    A database already at the baseline or later is backed up once, before
    its first pending migration, when db_path is given. A fresh database
    (version 0) has nothing to lose and is not backed up.

    Args:
        - conn (sqlite3.Connection): an autocommit connection.
        - migrations (Sequence[tuple[int, str]] | None): ordered (version,
          sql) pairs; the shipped set when None.
        - db_path (Path | None): the database file, for the backup; no
          backup is taken when None.

    Returns:
        - version (int): the schema version after migrating.

    Raises:
        - LegacyDatabaseError: the database holds the 0.2 schema.
        - SchemaVersionError: the database is newer than the known set.
        - MigrationError: the shipped files are malformed.
        - ForeignKeyCheckError: a migration left dangling references; it
          was rolled back.
        - MigrationFailedError: SQLite failed; the failing migration was
          rolled back.
        - OSError: the backup file could not be written.
    """
    ordered = load_migrations() if migrations is None else list(migrations)
    known = ordered[-1][0] if ordered else 0
    applying: int | None = None
    try:
        if is_legacy(conn):
            raise LegacyDatabaseError()
        current = user_version(conn)
        _refuse_newer(current, known)
        pending = [version for version, _ in ordered if version > current]
        if pending and current > 0 and db_path is not None:
            backup_database(conn, db_path, pending[-1])
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
                check_foreign_keys(conn)
                # PRAGMA takes no bound parameters; version is an int we parsed.
                conn.execute(f"PRAGMA user_version = {int(version)}")
            applying = None
        return user_version(conn)
    except sqlite3.Error as exc:
        raise MigrationFailedError(applying, exc) from exc


def _refuse_newer(found: int, known: int) -> None:
    if found > known:
        raise SchemaVersionError(found, known)
