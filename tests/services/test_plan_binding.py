"""A confirm token applies only the plan its preview showed."""

from collections.abc import Callable

import pytest

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.repositories.confirm import confirm_token_db
from xoot.services.bulk_service import apply_bulk, preview_bulk
from xoot.services.confirm_service import PLAN_CHANGED, hash_token, issue_token
from xoot.services.item_service import update_item
from xoot.services.session_close_service import close_session, preview_close
from xoot.services.subtree_service import apply_reparent, preview_reparent
from xoot.store.store import Store

DIGEST = "e" * 64
CLAUDE = Actor(kind=ActorKind.CLAUDE, client=Client.CODE)

type Apply = Callable[[Confirmation], object]
type PlanChanged = Callable[[int, str, str, Callable[[], object], Apply], None]


@pytest.fixture(name="session")
def fixture_session(project: Project, make_session: Callable[..., Session]) -> Session:
    """An open session with nothing linked."""
    return make_session(project)


@pytest.fixture(name="plan_changed")
def fixture_plan_changed(
    store: Store, row_counts: Callable[[], dict[str, int]]
) -> PlanChanged:
    """
    Factory: issue a token for a previewed plan, change the rows, then require
    the apply to be refused with nothing written and the token still unused.
    """

    def run(
        session_id: int,
        tool: str,
        plan_sha256: str,
        change: Callable[[], object],
        apply: Apply,
    ) -> None:
        token = issue_token(store, session_id, tool, DIGEST, plan_sha256)
        change()
        before = row_counts()
        claim = Confirmation(token=token, tool=tool, args_sha256=DIGEST)
        with pytest.raises(ConfirmTokenError, match=PLAN_CHANGED):
            apply(claim)
        assert row_counts() == before
        with store.read() as conn:
            row = confirm_token_db.get_by_hash(conn, hash_token(token))
        assert row is not None and row.used_at is None

    return run


def test_bulk_refused_when_keys_shift(
    store: Store,
    project: Project,
    session: Session,
    make_item: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """An item created after the preview shifts the planned keys; the apply is refused."""
    request = BulkCreate.model_validate({"items": [{"kind": "goal", "title": "g"}]})
    plan_changed(
        session.id,
        "items_create_bulk",
        preview_bulk(store, session.id, request).plan_sha256,
        lambda: make_item(project, ItemKind.GOAL),
        lambda claim: apply_bulk(store, session.id, request, CLAUDE, claim),
    )


def test_reparent_refused_when_the_subtree_grows(
    store: Store,
    project: Project,
    session: Session,
    make_item: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """A descendant added after the preview would move too; the apply is refused."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    target = make_item(project, ItemKind.GOAL)
    ctx = WriteContext(actor=CLAUDE, session_id=session.id)
    plan_changed(
        session.id,
        "item_update",
        preview_reparent(store, batch.id, target.id).plan_sha256,
        lambda: make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        lambda claim: apply_reparent(
            store, batch.id, target.id, batch.version, ctx, confirm=claim
        ),
    )


def test_close_refused_when_a_state_changes(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
    plan_changed: PlanChanged,
) -> None:
    """A carried-over item that moved state since the preview refuses the close."""
    item = make_item(project, ItemKind.SUBTASK)
    session = make_session(project, item.id)
    request = SessionClose(dispositions={item.id: Disposition.CARRY_OVER})
    ctx = WriteContext(actor=CLAUDE)
    plan_changed(
        session.id,
        "session_close",
        preview_close(store, session.id, request).plan_sha256,
        lambda: update_item(
            store, item.id, item.version, ItemUpdate(state="active"), ctx
        ),
        lambda claim: close_session(store, session.id, request, CLAUDE, claim),
    )


def test_close_refused_when_only_the_backlog_target_changes(
    store: Store,
    carried_backlog: tuple[Item, Session, SessionClose],
    plan_changed: PlanChanged,
) -> None:
    """
    A carried-over item moved from a session backlog to the project backlog
    keeps its state, yet refuses the close: the item would end differently.
    """
    item, session, request = carried_backlog
    ctx = WriteContext(actor=CLAUDE)
    plan_changed(
        session.id,
        "session_close",
        preview_close(store, session.id, request).plan_sha256,
        lambda: update_item(
            store, item.id, item.version, ItemUpdate(backlog_session_id=None), ctx
        ),
        lambda claim: close_session(store, session.id, request, CLAUDE, claim),
    )
