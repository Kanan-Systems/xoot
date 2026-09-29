"""backlog_push at every level, reparent re-keying, and old keys that still resolve."""

from collections.abc import Callable

import pytest

from xoot.exceptions.backlog_error import BacklogError
from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.repositories.item import item_alias_db
from xoot.services import key_resolver
from xoot.services.backlog_push_service import apply_push, preview_push
from xoot.services.confirm_service import issue_token
from xoot.services.decision_service import create_decision
from xoot.services.lookups import require_item
from xoot.services.subtree_service import apply_reparent, preview_reparent
from xoot.store.store import Store

type Tree = tuple[Item, Item, Item, Item]
DIGEST = "a" * 64


def _resolve(store: Store, project: Project, key: str) -> Item:
    with store.read() as conn:
        return key_resolver.item_by_key(conn, project.id, key)


def test_push_from_batch_to_goal_to_project(
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    capture_on: Callable[..., Item],
) -> None:
    """Each push takes the next number of the level above; old keys resolve."""
    goal, _, first, _ = work_tree
    capture_on(goal)
    item = capture_on(first)
    assert item.key == "goal-1/batch-1/backlog-1"
    plan = preview_push(store, item.id)
    assert plan.changes[0].after == {
        "number": 2,
        "key": "goal-1/backlog-2",
        "parent_id": goal.id,
    }
    apply_push(store, item.id, ctx, None)
    assert _resolve(store, project, "goal-1/backlog-2").id == item.id
    apply_push(store, item.id, ctx, None)
    moved = _resolve(store, project, "backlog-1")
    assert (moved.id, moved.parent_id) == (item.id, None)
    for old in ("goal-1/batch-1/backlog-1", "goal-1/backlog-2"):
        assert _resolve(store, project, old).id == item.id
    with store.read() as conn:
        assert item_alias_db.list_for_item(conn, item.id) == [
            "goal-1/batch-1/backlog-1",
            "goal-1/backlog-2",
        ]


def test_project_level_items_cannot_be_pushed(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """The project is the top: a push from there is refused."""
    goal, _, first, _ = work_tree
    item = capture_on(goal)
    apply_push(store, item.id, ctx, None)
    with pytest.raises(BacklogError, match="cannot be pushed further"):
        preview_push(store, item.id)
    with pytest.raises(BacklogError, match="not a backlog item"):
        preview_push(store, first.id)


def test_push_is_bound_to_its_preview(
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    capture_on: Callable[..., Item],
) -> None:
    """A token for a plan whose number was taken since is refused."""
    goal, _, first, _ = work_tree
    item = capture_on(first)
    plan = preview_push(store, item.id)
    token = issue_token(store, project.id, "backlog_push", DIGEST, plan.plan_sha256)
    capture_on(goal)
    claim = Confirmation(token=token, tool="backlog_push", args_sha256=DIGEST)
    with pytest.raises(ConfirmTokenError, match="plan changed"):
        apply_push(store, item.id, ctx, claim)
    plan = preview_push(store, item.id)
    token = issue_token(store, project.id, "backlog_push", DIGEST, plan.plan_sha256)
    claim = Confirmation(token=token, tool="backlog_push", args_sha256=DIGEST)
    applied, _ = apply_push(store, item.id, ctx, claim)
    assert applied.plan_sha256 == plan.plan_sha256


# Each fixture the test needs is one argument.
def test_reparent_rekeys_the_subtree_and_keeps_old_keys(  # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """A batch moved to another goal takes its next number; below follows."""
    _, batch, first, _ = work_tree
    backlog = capture_on(first)
    decision = create_decision(
        store, project.id, DecisionCreate(owner_item_id=first.id, title="d"), ctx
    )
    target = make_item(project, ItemKind.GOAL)
    make_item(project, ItemKind.BATCH, parent_id=target.id)
    plan = preview_reparent(store, batch.id, target.id)
    assert [(c.key, c.after["key"]) for c in plan.changes] == [
        ("goal-1/batch-1", "goal-2/batch-2"),
        ("goal-1/batch-1/subtask-1", "goal-2/batch-2/subtask-1"),
        ("goal-1/batch-1/subtask-2", "goal-2/batch-2/subtask-2"),
        ("goal-1/batch-1/backlog-1", "goal-2/batch-2/backlog-1"),
    ]
    apply_reparent(store, batch.id, target.id, batch.version, ctx)
    for old, new in [(c.key, c.after["key"]) for c in plan.changes]:
        assert _resolve(store, project, old).key == new
    with store.read() as conn:
        moved = key_resolver.decision_by_key(conn, project.id, decision.key)
        assert moved.key == "goal-2/batch-2/subtask-1/decision-1"
        assert require_item(conn, backlog.id).key == "goal-2/batch-2/backlog-1"


def test_reparent_refuses_backlog_items(
    store: Store, project: Project, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """Backlog moves only with push or cover."""
    goal, _, first, _ = work_tree
    with pytest.raises(HierarchyError, match="backlog_push"):
        preview_reparent(store, capture_on(first).id, goal.id)
    del project


def test_aliases_are_permanent_and_never_live(
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    capture_on: Callable[..., Item],
) -> None:
    """The schema refuses an alias naming a live key, and any alias delete."""
    goal, _, first, _ = work_tree
    item = capture_on(first)
    apply_push(store, item.id, ctx, None)
    with pytest.raises(IntegrityViolationError):
        with store.write() as conn:
            conn.execute("DELETE FROM item_alias")
    with pytest.raises(IntegrityViolationError):
        with store.write() as conn:
            conn.execute(
                "INSERT INTO item_alias VALUES (?, ?, ?, "
                "'2026-09-29T00:00:00.000000Z')",
                (project.id, goal.key, first.id),
            )
