"""D1-D3: confirm tokens are hashed, bound, single-use, short-lived and never logged."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.repositories.confirm import confirm_token_db
from xoot.services import confirm_service
from xoot.services.confirm_service import (
    TOKEN_TTL,
    consume_token,
    hash_token,
    issue_token,
)
from xoot.services.session_close_service import close_session
from xoot.services.subtree_service import apply_drop, preview_drop
from xoot.store.store import Store

DIGEST = "a" * 64
PLAN = "d" * 64
OTHER_DIGEST = "b" * 64
TOOL = "session_close"


@pytest.fixture(name="session")
def fixture_session(project: Project, make_session: Callable[..., Session]) -> Session:
    """An open session with nothing linked."""
    return make_session(project)


def _claim(token: str, tool: str = TOOL, digest: str = DIGEST) -> Confirmation:
    return Confirmation(token=token, tool=tool, args_sha256=digest)


def _consume(store: Store, claim: Confirmation, session_id: int) -> None:
    with store.write() as conn:
        consume_token(conn, claim, session_id)


def test_only_the_digest_is_stored(store: Store, session: Session) -> None:
    """The row holds the token's SHA-256, never the token itself."""
    token = issue_token(store, session.id, TOOL, DIGEST, PLAN)
    assert len(token) >= 22
    rows = store.conn.execute("SELECT * FROM confirm_token").fetchall()
    assert len(rows) == 1
    assert rows[0]["token_sha256"] == hash_token(token)
    assert all(token not in str(value) for value in tuple(rows[0]))


def test_consume_marks_used_once(store: Store, session: Session) -> None:
    """A good token is consumed once; replaying it fails."""
    token = issue_token(store, session.id, TOOL, DIGEST, PLAN)
    _consume(store, _claim(token), session.id)
    with store.read() as conn:
        row = confirm_token_db.get_by_hash(conn, hash_token(token))
    assert row is not None and row.used_at is not None
    with pytest.raises(ConfirmTokenError, match="already been used"):
        _consume(store, _claim(token), session.id)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"tool": "item_update"}, "another tool"),
        ({"digest": OTHER_DIGEST}, "does not match these arguments"),
    ],
)
def test_mismatched_claims_fail(
    store: Store, session: Session, change: dict[str, str], reason: str
) -> None:
    """A token only applies to the tool and arguments it was issued for."""
    token = issue_token(store, session.id, TOOL, DIGEST, PLAN)
    with pytest.raises(ConfirmTokenError, match=reason):
        _consume(store, _claim(token, **change), session.id)


def test_other_session_fails(
    store: Store,
    project: Project,
    session: Session,
    make_session: Callable[..., Session],
) -> None:
    """A token issued in one session cannot be used from another."""
    token = issue_token(store, session.id, TOOL, DIGEST, PLAN)
    other = make_session(project)
    with pytest.raises(ConfirmTokenError, match="another session"):
        _consume(store, _claim(token), other.id)


def test_unknown_token_fails(store: Store, session: Session) -> None:
    """A token that was never issued is refused."""
    with pytest.raises(ConfirmTokenError, match="unknown"):
        _consume(store, _claim("never-issued-token"), session.id)


def test_expired_token_fails(
    store: Store, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once the clock passes the TTL the token is refused and stays unused."""
    issued = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    token = issue_token(store, session.id, TOOL, DIGEST, PLAN, now=issued)

    clock = SimpleNamespace(now=lambda tz: issued + TOKEN_TTL)
    monkeypatch.setattr(confirm_service, "datetime", clock)
    with pytest.raises(ConfirmTokenError, match="expired"):
        _consume(store, _claim(token), session.id)
    with store.read() as conn:
        row = confirm_token_db.get_by_hash(conn, hash_token(token))
    assert row is not None and row.used_at is None


def test_closed_session_gets_no_token(
    store: Store, user: Actor, session: Session
) -> None:
    """Tokens are only issued for open sessions."""
    close_session(store, session.id, SessionClose(), user)
    with pytest.raises(SessionStateError):
        issue_token(store, session.id, TOOL, DIGEST, PLAN)


def test_failed_apply_leaves_token_unused(
    store: Store,
    project: Project,
    session: Session,
    claude: Actor,
    make_item: Callable[..., Item],
) -> None:
    """The token is consumed in the apply's transaction, so a failed apply keeps it."""
    goal = make_item(project, ItemKind.GOAL)
    make_item(project, ItemKind.BATCH, parent_id=goal.id)
    ctx = WriteContext(actor=claude, session_id=session.id)
    plan = preview_drop(store, goal.id)
    token = issue_token(store, session.id, "item_update", DIGEST, plan.plan_sha256)
    claim = _claim(token, tool="item_update")
    with pytest.raises(VersionConflictError):
        apply_drop(store, goal.id, goal.version + 1, ctx, claim)
    plan = apply_drop(store, goal.id, goal.version, ctx, claim)
    assert len(plan.changes) == 2
    with pytest.raises(ConfirmTokenError, match="already been used"):
        apply_drop(store, goal.id, goal.version + 1, ctx, claim)


def test_token_is_never_logged(
    store: Store, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Issuing and consuming log nothing that contains the token."""
    with caplog.at_level(logging.DEBUG):
        token = issue_token(store, session.id, TOOL, DIGEST, PLAN)
        _consume(store, _claim(token), session.id)
    assert token not in caplog.text
