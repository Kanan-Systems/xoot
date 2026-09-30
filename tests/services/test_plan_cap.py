"""Move, push and drop plans are refused at plan time past MAX_PLAN_ITEMS."""

from collections.abc import Callable

import pytest

from xoot.exceptions.plan_size_error import PlanSizeError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import MAX_PLAN_ITEMS
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services import plan_cap
from xoot.services.backlog_push_service import apply_push, preview_push
from xoot.services.item_service import create_item_in
from xoot.services.subtree_service import (
    apply_drop,
    apply_reparent,
    preview_drop,
    preview_reparent,
)
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def _batch_of(
    store: Store, ctx: WriteContext, project: Project, goal: Item, size: int
) -> Item:
    """A batch holding size - 1 open subtasks: a subtree of exactly size items."""
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        batch = create_item_in(
            scope,
            project.id,
            ItemCreate(kind=ItemKind.BATCH, title="big", parent_id=goal.id),
        )
        for number in range(size - 1):
            create_item_in(
                scope,
                project.id,
                ItemCreate(
                    kind=ItemKind.SUBTASK, title=f"s{number}", parent_id=batch.id
                ),
            )
    return batch


def test_the_cap_is_200() -> None:
    """The constant sits next to the bulk cap."""
    assert MAX_PLAN_ITEMS == 200


def test_reparent_at_the_cap_passes_and_one_more_is_refused(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """A 200-item move previews and applies; a 201-item one is refused both ways."""
    goal = make_item(project, ItemKind.GOAL)
    target = make_item(project, ItemKind.GOAL)
    fits = _batch_of(store, ctx, project, goal, MAX_PLAN_ITEMS)
    assert len(preview_reparent(store, fits.id, target.id).changes) == MAX_PLAN_ITEMS
    plan, _ = apply_reparent(store, fits.id, target.id, fits.version, ctx)
    assert len(plan.changes) == MAX_PLAN_ITEMS
    over = _batch_of(store, ctx, project, goal, MAX_PLAN_ITEMS + 1)
    with pytest.raises(PlanSizeError, match=f"{MAX_PLAN_ITEMS + 1} items"):
        preview_reparent(store, over.id, target.id)
    with pytest.raises(PlanSizeError):
        apply_reparent(store, over.id, target.id, over.version, ctx)


def test_drop_at_the_cap_passes_and_one_more_is_refused(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Dropping 200 open items works; 201 is refused and writes nothing."""
    goal = make_item(project, ItemKind.GOAL)
    fits = _batch_of(store, ctx, project, goal, MAX_PLAN_ITEMS)
    plan, _ = apply_drop(store, fits.id, fits.version, ctx)
    assert len(plan.changes) == MAX_PLAN_ITEMS
    over = _batch_of(store, ctx, project, goal, MAX_PLAN_ITEMS + 1)
    with pytest.raises(PlanSizeError):
        preview_drop(store, over.id)
    with pytest.raises(PlanSizeError):
        apply_drop(store, over.id, over.version, ctx)
    with store.read() as conn:
        open_left = conn.execute(
            "SELECT count(*) FROM item WHERE parent_id = ? AND state = 'open'",
            (over.id,),
        ).fetchone()[0]
    assert open_left == MAX_PLAN_ITEMS


def test_push_plans_pass_the_same_cap(
    store: Store,
    ctx: WriteContext,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A push moves one item, so the cap is shown by lowering it below one."""
    item = capture_on(work_tree[2])
    monkeypatch.setattr(plan_cap, "MAX_PLAN_ITEMS", 0)
    with pytest.raises(PlanSizeError, match="at most 0"):
        preview_push(store, item.id)
    with pytest.raises(PlanSizeError):
        apply_push(store, item.id, ctx, None)
