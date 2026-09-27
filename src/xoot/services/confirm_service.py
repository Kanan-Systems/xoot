"""
Issuing and consuming confirm tokens for two-phase writes.

A preview issues a token bound to one tool, one argument digest and one open
session. The apply presents it inside its own write transaction, which checks
and consumes it first, so the token is spent only if the write commits.
"""

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.new_confirm_token import NewConfirmToken
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.confirm import confirm_token_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_session
from xoot.store.store import Store

TOKEN_TTL = timedelta(minutes=5)
# 16 random bytes: 128 bits, far beyond guessing within the TTL.
TOKEN_BYTES = 16


def hash_token(token: str) -> str:
    """
    Digest a token the way it is stored.

    Args:
        - token (str): the token as the caller holds it.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(
    store: Store,
    session_id: int,
    tool: str,
    args_sha256: str,
    now: datetime | None = None,
) -> str:
    """
    Create a single-use token that authorizes one previewed write.

    Args:
        - store (Store): the database.
        - session_id (int): the open session the write belongs to.
        - tool (str): the tool the token is valid for.
        - args_sha256 (str): digest of the previewed call's arguments.
        - now (datetime | None): issue time; the current UTC time when None.

    Returns:
        - token (str): the token; only its digest is stored.

    Raises:
        - InvalidIdError: session_id is not an int id.
        - NotFoundError: no such session.
        - SessionStateError: the session is closed.
        - pydantic.ValidationError: tool or args_sha256 is malformed.
    """
    check_id("session_id", session_id)
    issued_at = datetime.now(UTC) if now is None else now
    token = secrets.token_urlsafe(TOKEN_BYTES)
    new = NewConfirmToken(
        token_sha256=hash_token(token),
        tool=tool,
        args_sha256=args_sha256,
        session_id=session_id,
        expires_at=issued_at + TOKEN_TTL,
    )
    with store.write() as conn:
        if require_session(conn, session_id).status is not SessionStatus.OPEN:
            raise SessionStateError(f"session {session_id} is closed")
        confirm_token_db.insert(conn, new)
    return token


def consume_token(
    conn: sqlite3.Connection,
    confirmation: Confirmation,
    session_id: int | None,
    now: datetime | None = None,
) -> None:
    """
    Check a presented token and mark it used.

    Must run inside the write transaction of the change it authorizes, so a
    failed write rolls the use back and the token stays valid.

    Args:
        - conn (sqlite3.Connection): connection inside that transaction.
        - confirmation (Confirmation): the token, tool and argument digest.
        - session_id (int | None): the session of the write.
        - now (datetime | None): use time; the current UTC time when None.

    Raises:
        - ConfirmTokenError: the token is unknown, bound to another tool,
          session or arguments, already used, or expired.
    """
    used_at = datetime.now(UTC) if now is None else now
    row = confirm_token_db.get_by_hash(conn, hash_token(confirmation.token))
    if row is None:
        raise ConfirmTokenError("the confirm token is unknown")
    if row.tool != confirmation.tool:
        raise ConfirmTokenError("the confirm token was issued for another tool")
    if row.session_id != session_id:
        raise ConfirmTokenError("the confirm token was issued for another session")
    if row.args_sha256 != confirmation.args_sha256:
        raise ConfirmTokenError("the confirm token does not match these arguments")
    if row.used_at is not None:
        raise ConfirmTokenError("the confirm token has already been used")
    if used_at >= row.expires_at:
        raise ConfirmTokenError("the confirm token has expired")
    confirm_token_db.mark_used(conn, row.id, used_at)
