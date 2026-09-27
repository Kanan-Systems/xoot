"""SQL access for the confirm_token table."""

import sqlite3
from datetime import datetime

from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.models.confirm.confirm_token import ConfirmToken
from xoot.models.confirm.new_confirm_token import NewConfirmToken
from xoot.models.fields import format_timestamp

_COLUMNS = "id, token_sha256, tool, args_sha256, session_id, expires_at, used_at"


def insert(conn: sqlite3.Connection, new: NewConfirmToken) -> ConfirmToken:
    """
    Store a new, unused token.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewConfirmToken): the token digest and what it is bound to.

    Returns:
        - token (ConfirmToken): the stored row.
    """
    row = conn.execute(
        "INSERT INTO confirm_token (token_sha256, tool, args_sha256, session_id, "
        "expires_at) VALUES (:token_sha256, :tool, :args_sha256, :session_id, "
        f":expires_at) RETURNING {_COLUMNS}",
        new.model_dump(mode="json"),
    ).fetchone()
    return ConfirmToken.model_validate(dict(row))


def get_by_hash(conn: sqlite3.Connection, token_sha256: str) -> ConfirmToken | None:
    """
    Fetch a token by the SHA-256 of its value.

    Args:
        - conn (sqlite3.Connection): open connection.
        - token_sha256 (str): hex digest of the presented token.

    Returns:
        - token (ConfirmToken | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM confirm_token WHERE token_sha256 = ?",
        (token_sha256,),
    ).fetchone()
    return None if row is None else ConfirmToken.model_validate(dict(row))


def mark_used(conn: sqlite3.Connection, token_id: int, used_at: datetime) -> None:
    """
    Stamp a token as used, only if it is still unused.

    Args:
        - conn (sqlite3.Connection): connection inside the write transaction
          the token authorizes.
        - token_id (int): the token row id.
        - used_at (datetime): when it was used.

    Raises:
        - StaleWriteError: the token was used inside what should have been
          an exclusive transaction.
    """
    cursor = conn.execute(
        "UPDATE confirm_token SET used_at = ? WHERE id = ? AND used_at IS NULL",
        (format_timestamp(used_at), token_id),
    )
    if cursor.rowcount != 1:
        raise StaleWriteError(
            f"confirm token {token_id} changed during the transaction"
        )
