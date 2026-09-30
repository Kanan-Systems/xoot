"""A confirm token applies only the plan its preview showed."""

from collections.abc import Callable

import pytest

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.repositories.confirm import confirm_token_db
from xoot.services.backlog_push_service import apply_push, preview_push
from xoot.services.bulk_service import apply_bulk, preview_bulk
from xoot.services.confirm_service import PLAN_CHANGED, hash_token, issue_token
from xoot.services.subtree_service import (
    apply_drop,
    apply_reparent,
    preview_drop,
    preview_reparent,
)
from xoot.store.store import Store

DIGEST = "e" * 64
CLAUDE = WriteContext(actor=Actor(kind=ActorKind.CLAUDE, client=Client.CODE))

type Apply = Callable[[Confirmation], object]
type PlanChanged = Callable[[int, str, str, Callable[[], object], Apply], None]


@pytest.fixture(name="plan_changed")
def fixture_plan_changed(
    store: Store, row_counts: Callable[[], dict[str, int]]
) -> PlanChanged:
    """
    Factory: issue a token for a previewed plan, change the rows, then require
    the apply to be refused with nothing written and the token still unused.
    """

    def run(
        project_id: int,
        tool: str,
        plan_sha256: str,
        change: Callable[[], object],
        apply: Apply,
    ) -> None:
        token = issue_token(
            store, project_id, tool, DIGEST, plan_sha256, actor=CLAUDE.actor
        )
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
    make_item: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """A goal created after the preview shifts the planned keys; the apply is refused."""
    request = BulkCreate.model_validate({"items": [{"kind": "goal", "title": "g"}]})
    plan_changed(
        project.id,
        "items_create_bulk",
        preview_bulk(store, project.id, request).plan_sha256,
        lambda: make_item(project, ItemKind.GOAL),
        lambda claim: apply_bulk(store, project.id, request, CLAUDE, claim),
    )


def test_reparent_refused_when_the_subtree_grows(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """A descendant added after the preview would move too; the apply is refused."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    target = make_item(project, ItemKind.GOAL)
    plan_changed(
        project.id,
        "item_update",
        preview_reparent(store, batch.id, target.id).plan_sha256,
        lambda: make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        lambda claim: apply_reparent(
            store, batch.id, target.id, batch.version, CLAUDE, confirm=claim
        ),
    )


def test_drop_refused_when_a_child_is_added(
    store: Store,
    project: Project,
    work_tree: tuple[Item, Item, Item, Item],
    make_item: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """A new subtask would be dropped too; the apply is refused."""
    _, batch, _, _ = work_tree
    plan_changed(
        project.id,
        "item_update",
        preview_drop(store, batch.id).plan_sha256,
        lambda: make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        lambda claim: apply_drop(store, batch.id, batch.version, CLAUDE, claim),
    )


def test_push_refused_when_the_target_number_is_taken(
    store: Store,
    project: Project,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
    plan_changed: PlanChanged,
) -> None:
    """The goal handed out the planned number meanwhile; the push is refused."""
    goal, _, first, _ = work_tree
    item = capture_on(first)
    plan_changed(
        project.id,
        "backlog_push",
        preview_push(store, item.id).plan_sha256,
        lambda: capture_on(goal),
        lambda claim: apply_push(store, item.id, CLAUDE, claim),
    )
