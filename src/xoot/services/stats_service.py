"""
Read-only statistics about the database file: pages, sizes, row counts and
the schema version.

Everything is read from one snapshot, so the row counts agree with each
other; file sizes come from the filesystem and are reported as found.
"""

import os
from pathlib import Path

from xoot.models.store.db_stats import DbStats
from xoot.store.migrator import SCHEMA_VERSION
from xoot.store.store import Store


def db_stats(store: Store) -> DbStats:
    """
    Describe the database: page and free-page counts, file sizes, row counts,
    and its schema version beside the newest one this code knows.

    Args:
        - store (Store): the database.

    Returns:
        - stats (DbStats): the snapshot.

    Raises:
        - DatabaseAccessError: SQLite could not read the database.
        - MigrationError: the shipped migration files are malformed.
    """
    with store.read() as conn:
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
            )
        ]
        # Table names come from sqlite_schema itself, never from input.
        rows = {
            table: int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
            for table in tables
        }
    return DbStats(
        path=str(store.path),
        page_count=page_count,
        freelist_count=freelist_count,
        db_bytes=_size(store.path),
        wal_bytes=_size(store.path.with_name(store.path.name + "-wal")),
        rows=rows,
        schema_version=schema_version,
        known_schema_version=SCHEMA_VERSION,
    )


def _size(path: Path) -> int:
    try:
        return os.stat(path).st_size
    except FileNotFoundError:
        return 0
