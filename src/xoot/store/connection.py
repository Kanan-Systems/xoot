"""
Opening SQLite connections with the pragmas every service relies on.

Foreign keys enforce same-project references, WAL lets readers run beside
the single writer, and secure_delete zeroes freed bytes so replaced or
redacted text does not linger on disk. If any of these does not take effect
the connection is refused rather than used unsafely.
"""

import sqlite3
import time
from pathlib import Path

from xoot.exceptions.pragma_check_error import PragmaCheckError

BUSY_TIMEOUT_MS = 5000
_RETRY_SLEEP_S = 0.01

PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA secure_delete = ON",
)


def connect(path: Path) -> sqlite3.Connection:
    """
    Open a connection in autocommit mode with the required pragmas.

    Transactions are always explicit (see store.transaction), so the driver
    must not open implicit ones.

    Args:
        - path (Path): the database file.

    Returns:
        - connection (sqlite3.Connection): a verified connection.

    Raises:
        - PragmaCheckError: foreign_keys, journal_mode or secure_delete did
          not take effect.
        - sqlite3.Error: the database could not be opened.
    """
    conn = sqlite3.connect(path, autocommit=True, timeout=BUSY_TIMEOUT_MS / 1000)
    try:
        deadline = time.monotonic() + BUSY_TIMEOUT_MS / 1000
        for statement in PRAGMAS:
            _execute_until(conn, statement, deadline)
        verify_pragmas(conn)
    except BaseException:
        conn.close()
        raise
    conn.row_factory = sqlite3.Row
    return conn


def verify_pragmas(conn: sqlite3.Connection) -> None:
    """
    Read back the safety pragmas and fail closed on any mismatch.

    Args:
        - conn (sqlite3.Connection): the connection to check.

    Raises:
        - PragmaCheckError: foreign_keys is not 1, journal_mode is not wal,
          or secure_delete is not 1 (FAST, 2, skips some freed pages).
    """
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    secure_delete = conn.execute("PRAGMA secure_delete").fetchone()[0]
    if foreign_keys != 1 or journal_mode != "wal" or secure_delete != 1:
        raise PragmaCheckError(
            f"unsafe connection: foreign_keys={foreign_keys}, "
            f"journal_mode={journal_mode}, secure_delete={secure_delete}"
        )


def _execute_until(conn: sqlite3.Connection, statement: str, deadline: float) -> None:
    """
    Run a pragma, retrying SQLITE_BUSY until the deadline.

    Two connections switching a fresh file to WAL at once can deadlock on the
    lock upgrade; SQLite then returns BUSY without calling the busy handler,
    so busy_timeout alone does not cover it. WAL is persistent in the file,
    so this only happens while the database is first created.
    """
    while True:
        try:
            conn.execute(statement)
            return
        except sqlite3.OperationalError as exc:
            busy = exc.sqlite_errorcode & 0xFF == sqlite3.SQLITE_BUSY
            if not busy or time.monotonic() >= deadline:
                raise
        time.sleep(_RETRY_SLEEP_S)
