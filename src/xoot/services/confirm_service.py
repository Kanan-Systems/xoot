"""
Issuing and consuming confirm tokens for two-phase writes.

A preview issues a token bound to one project, one tool, one argument
digest and one plan digest. The apply presents it inside its own write
transaction, which checks and consumes it first, then re-plans and compares
the plan digest before writing, so the token is spent only if the write
commits, and only for the plan the preview showed.
"""

import hashlib
import secrets
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.models.confirm.confirm_token import ConfirmToken
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.confirm.new_confirm_token import NewConfirmToken
from xoot.models.confirm.plan_entry import PlanEntry
from xoot.repositories.confirm import confirm_token_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_project
from xoot.store.store import Store
from xoot.utils.utils import canonical_sha256

TOKEN_TTL = timedelta(minutes=5)
# 16 random bytes: 128 bits, far beyond guessing within the TTL.
TOKEN_BYTES = 16
# Spent tokens are kept this long after issue, then pruned by the next issue.
PRUNE_AGE = timedelta(days=1)
PLAN_CHANGED = "plan changed since preview; preview again"


def hash_token(token: str) -> str:
    """
    Digest a token the way it is stored.

    Args:
        - token (str): the token as the caller holds it.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def plan_digest(entries: Iterable[PlanEntry]) -> str:
    """
    Digest a plan as the post-apply entry of every item it touches.

    Two plans that would leave any affected item different in any column
    the apply writes digest differently. Entry order does not matter.

    Args:
        - entries (Iterable[PlanEntry]): one entry per affected item.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    rows = [entry.model_dump(mode="json") for entry in entries]
    return canonical_sha256(sorted(rows, key=canonical_sha256))


# One parameter per bound value, plus the clock override tests use.
def issue_token(  # pylint: disable=too-many-arguments
    store: Store,
    project_id: int,
    tool: str,
    args_sha256: str,
    plan_sha256: str,
    *,
    now: datetime | None = None,
) -> str:
    """
    Create a single-use token that authorizes one previewed write.

    Spent tokens issued more than PRUNE_AGE ago are deleted first, in the
    same transaction, so the table does not grow without bound.

    Args:
        - store (Store): the database.
        - project_id (int): the project the write belongs to.
        - tool (str): the tool the token is valid for.
        - args_sha256 (str): digest of the previewed call's arguments.
        - plan_sha256 (str): plan_digest of the previewed plan.
        - now (datetime | None): issue time; the current UTC time when None.

    Returns:
        - token (str): the token; only its digest is stored.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: no such project.
        - pydantic.ValidationError: tool or a digest is malformed.
    """
    check_id("project_id", project_id)
    issued_at = datetime.now(UTC) if now is None else now
    token = secrets.token_urlsafe(TOKEN_BYTES)
    new = NewConfirmToken(
        token_sha256=hash_token(token),
        project_id=project_id,
        tool=tool,
        args_sha256=args_sha256,
        plan_sha256=plan_sha256,
        expires_at=issued_at + TOKEN_TTL,
    )
    with store.write() as conn:
        require_project(conn, project_id)
        # No issue time is stored; it is always expires_at - TOKEN_TTL.
        confirm_token_db.delete_spent(
            conn, issued_at, issued_at - PRUNE_AGE + TOKEN_TTL
        )
        confirm_token_db.insert(conn, new)
    return token


def consume_token(
    conn: sqlite3.Connection,
    confirmation: Confirmation,
    project_id: int,
    now: datetime | None = None,
) -> ConfirmToken:
    """
    Check a presented token and mark it used.

    Must run inside the write transaction of the change it authorizes, so a
    failed write rolls the use back and the token stays valid. The caller
    then re-plans and passes the result to check_plan before writing.

    Args:
        - conn (sqlite3.Connection): connection inside that transaction.
        - confirmation (Confirmation): the token, tool and argument digest.
        - project_id (int): the project of the write.
        - now (datetime | None): use time; the current UTC time when None.

    Returns:
        - token (ConfirmToken): the row, for check_plan.

    Raises:
        - ConfirmTokenError: the token is unknown, bound to another tool,
          project or arguments, already used, or expired.
    """
    used_at = datetime.now(UTC) if now is None else now
    row = confirm_token_db.get_by_hash(conn, hash_token(confirmation.token))
    if row is None:
        raise ConfirmTokenError("the confirm token is unknown")
    if row.tool != confirmation.tool:
        raise ConfirmTokenError("the confirm token was issued for another tool")
    if row.project_id != project_id:
        raise ConfirmTokenError("the confirm token was issued for another project")
    if row.args_sha256 != confirmation.args_sha256:
        raise ConfirmTokenError("the confirm token does not match these arguments")
    if row.used_at is not None:
        raise ConfirmTokenError("the confirm token has already been used")
    if used_at >= row.expires_at:
        raise ConfirmTokenError("the confirm token has expired")
    confirm_token_db.mark_used(conn, row.id, used_at)
    return row


def check_plan(token: ConfirmToken | None, plan_sha256: str) -> None:
    """
    Refuse an apply whose freshly computed plan differs from the preview's.

    Raising inside the apply's transaction rolls back the token's use too,
    so the token stays unused and nothing is written.

    Args:
        - token (ConfirmToken | None): the consumed token; None when the call
          needed no confirmation.
        - plan_sha256 (str): plan_digest of the plan about to be written.

    Raises:
        - ConfirmTokenError: the plan changed since the preview.
    """
    if token is not None and token.plan_sha256 != plan_sha256:
        raise ConfirmTokenError(PLAN_CHANGED)
