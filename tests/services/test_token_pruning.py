"""Issuing a token prunes spent tokens issued more than a day ago."""

from datetime import UTC, datetime, timedelta

from xoot.models.confirm.new_confirm_token import NewConfirmToken
from xoot.models.project.project import Project
from xoot.repositories.confirm import confirm_token_db
from xoot.services.confirm_service import TOKEN_TTL, hash_token, issue_token
from xoot.store.store import Store

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
DIGEST = "f" * 64


def _backdated(
    store: Store, project: Project, name: str, issued: datetime, used: bool
) -> None:
    """Insert a token row as if issued at `issued`; the name fills its hash."""
    with store.write() as conn:
        row = confirm_token_db.insert(
            conn,
            NewConfirmToken(
                token_sha256=name * 64,
                project_id=project.id,
                tool="backlog_push",
                args_sha256=DIGEST,
                plan_sha256=DIGEST,
                expires_at=issued + TOKEN_TTL,
            ),
        )
        if used:
            confirm_token_db.mark_used(conn, row.id, issued + timedelta(minutes=1))


def test_issue_prunes_only_old_spent_tokens(store: Store, project: Project) -> None:
    """Old expired and old used rows go; recent spent rows and live rows stay."""
    day = timedelta(days=1)
    _backdated(store, project, "a", NOW - 2 * day, used=False)
    _backdated(store, project, "b", NOW - 2 * day, used=True)
    _backdated(store, project, "c", NOW - day - timedelta(minutes=1), used=False)
    _backdated(store, project, "d", NOW - day + timedelta(minutes=1), used=False)
    _backdated(store, project, "e", NOW - timedelta(hours=1), used=True)
    _backdated(store, project, "f", NOW - timedelta(minutes=1), used=False)
    token = issue_token(store, project.id, "backlog_push", DIGEST, DIGEST, now=NOW)
    with store.read() as conn:
        left = {
            row["token_sha256"]
            for row in conn.execute("SELECT token_sha256 FROM confirm_token")
        }
    # "d" expired but was issued less than a day ago; "f" is still live.
    assert left == {"d" * 64, "e" * 64, "f" * 64, hash_token(token)}
