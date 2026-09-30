"""A confirm token applies only for the actor kind and client that previewed."""

import pytest

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.project.project import Project
from xoot.repositories.confirm import confirm_token_db
from xoot.services.confirm_service import consume_token, hash_token, issue_token
from xoot.store.store import Store

DIGEST = "a" * 64
PLAN = "d" * 64
TOOL = "backlog_push"
CODE = Actor(kind=ActorKind.CLAUDE, client=Client.CODE)
CHAT = Actor(kind=ActorKind.CLAUDE, client=Client.CHAT)
DASHBOARD = Actor(kind=ActorKind.USER, client=Client.DASHBOARD)
CLI = Actor(kind=ActorKind.USER, client=Client.CLI)


def _consume(store: Store, token: str, project: Project, actor: Actor) -> None:
    claim = Confirmation(token=token, tool=TOOL, args_sha256=DIGEST)
    with store.write() as conn:
        consume_token(conn, claim, project.id, actor)


def _used(store: Store, token: str) -> bool:
    with store.read() as conn:
        row = confirm_token_db.get_by_hash(conn, hash_token(token))
    assert row is not None
    return row.used_at is not None


def test_the_row_records_who_previewed(store: Store, project: Project) -> None:
    """actor_kind and client are stored with the token's digest."""
    token = issue_token(store, project.id, TOOL, DIGEST, PLAN, actor=DASHBOARD)
    with store.read() as conn:
        row = confirm_token_db.get_by_hash(conn, hash_token(token))
    assert row is not None
    assert (row.actor_kind, row.client) == (ActorKind.USER, Client.DASHBOARD)


@pytest.mark.parametrize(
    ("issued_to", "applied_by"),
    [(CODE, CHAT), (CODE, DASHBOARD), (DASHBOARD, CODE), (DASHBOARD, CLI), (CLI, CODE)],
)
def test_another_client_or_kind_cannot_apply(
    store: Store, project: Project, issued_to: Actor, applied_by: Actor
) -> None:
    """Any other kind or client is refused and the token stays unused."""
    token = issue_token(store, project.id, TOOL, DIGEST, PLAN, actor=issued_to)
    with pytest.raises(ConfirmTokenError, match="another client"):
        _consume(store, token, project, applied_by)
    assert not _used(store, token)
    _consume(store, token, project, issued_to)
    assert _used(store, token)
