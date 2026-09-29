"""Subtree drop and reparent, each a pure preview plus a re-validating apply."""

from collections.abc import Callable

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.item_service import get_item
from xoot.services.subtree_service import (
    apply_drop,
    apply_reparent,
    preview_drop,
    preview_reparent,
)
from xoot.store.store import Store


@pytest.fixture(name="tree")
def fixture_tree(project: Project, make_item: Callable[..., Item]) -> dict[str, Item]:
    """goal > batch > (open subtask, done subtask), plus a second goal."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    return {
        "goal": goal,
        "batch": batch,
        "open": make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        "done": make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="done"),
        "goal2": make_item(project, ItemKind.GOAL),
    }


def test_drop_preview_writes_nothing(
    store: Store, tree: dict[str, Item], row_counts: Callable[[], dict[str, int]]
) -> None:
    """The preview lists every open item in the subtree, deepest first."""
    before, changes = row_counts(), store.conn.total_changes
    plan = preview_drop(store, tree["goal"].id)
    assert (row_counts(), store.conn.total_changes) == (before, changes)
    assert [c.item_id for c in plan.changes] == [
        tree[k].id for k in ("open", "batch", "goal")
    ]
    assert all(c.after == {"state": "dropped"} for c in plan.changes)


def test_drop_apply_writes_the_plan_and_completes_nothing_inside(
    store: Store, tree: dict[str, Item], ctx: WriteContext
) -> None:
    """Apply drops the same items; done items keep their state; no completion."""
    preview = preview_drop(store, tree["goal"].id)
    applied, report = apply_drop(store, tree["goal"].id, 1, ctx)
    assert applied == preview
    assert report.completed == () and report.reopened == ()
    assert [
        get_item(store, tree[k].id).state for k in ("goal", "batch", "open", "done")
    ] == ["dropped", "dropped", "dropped", "done"]
    assert get_item(store, tree["goal2"].id) == tree["goal2"]


def test_dropping_the_last_open_batch_completes_its_goal(
    store: Store,
    project: Project,
    tree: dict[str, Item],
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """Above the dropped root the engine runs as usual."""
    other = make_item(project, ItemKind.BATCH, parent_id=tree["goal"].id)
    make_item(project, ItemKind.SUBTASK, parent_id=other.id, state="done")
    _, report = apply_drop(store, tree["batch"].id, 1, ctx)
    assert report.completed == (tree["goal"].key,)
    assert get_item(store, tree["goal"].id).state == "done"


def test_apply_revalidates_against_current_rows(
    store: Store,
    project: Project,
    tree: dict[str, Item],
    make_item: Callable[..., Item],
    ctx: WriteContext,
) -> None:
    """Apply re-plans: a child added after the preview is dropped too."""
    preview = preview_drop(store, tree["batch"].id)
    late = make_item(project, ItemKind.SUBTASK, parent_id=tree["batch"].id)
    applied, _ = apply_drop(store, tree["batch"].id, 1, ctx)
    assert late.id in {c.item_id for c in applied.changes} - {
        c.item_id for c in preview.changes
    }


def test_drop_checks_the_root_version(
    store: Store, tree: dict[str, Item], ctx: WriteContext
) -> None:
    """A stale root version refuses the whole drop."""
    with pytest.raises(VersionConflictError):
        apply_drop(store, tree["goal"].id, 7, ctx)
    assert get_item(store, tree["open"].id).state == "open"


def test_reparent_preview(
    store: Store, tree: dict[str, Item], row_counts: Callable[[], dict[str, int]]
) -> None:
    """The root's parent, number and key change, then each descendant's key."""
    before = row_counts()
    plan = preview_reparent(store, tree["batch"].id, tree["goal2"].id)
    assert row_counts() == before
    assert [(c.item_id, c.before, c.after) for c in plan.changes] == [
        (
            tree["batch"].id,
            {"parent_id": tree["goal"].id, "key": "goal-1/batch-1", "number": 1},
            {"parent_id": tree["goal2"].id, "key": "goal-2/batch-1", "number": 1},
        ),
        (
            tree["open"].id,
            {"key": "goal-1/batch-1/subtask-1"},
            {"key": "goal-2/batch-1/subtask-1"},
        ),
        (
            tree["done"].id,
            {"key": "goal-1/batch-1/subtask-2"},
            {"key": "goal-2/batch-1/subtask-2"},
        ),
    ]


def test_reparent_apply(store: Store, tree: dict[str, Item], ctx: WriteContext) -> None:
    """Apply moves the root and re-keys the children under it."""
    plan, _ = apply_reparent(store, tree["batch"].id, tree["goal2"].id, 1, ctx)
    assert len(plan.changes) == 3
    moved = get_item(store, tree["batch"].id)
    assert (moved.parent_id, moved.key) == (tree["goal2"].id, "goal-2/batch-1")
    child = get_item(store, tree["open"].id)
    assert (child.parent_id, child.key) == (
        tree["batch"].id,
        "goal-2/batch-1/subtask-1",
    )


def test_reparent_a_subtask_to_another_batch(
    store: Store,
    project: Project,
    tree: dict[str, Item],
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """A subtask takes the next number of its new batch."""
    target = make_item(project, ItemKind.BATCH, parent_id=tree["goal2"].id)
    make_item(project, ItemKind.SUBTASK, parent_id=target.id)
    apply_reparent(store, tree["open"].id, target.id, 1, ctx)
    assert get_item(store, tree["open"].id).key == "goal-2/batch-1/subtask-2"


def test_reparent_enforces_the_hierarchy(
    store: Store,
    other_project: Project,
    tree: dict[str, Item],
    make_item: Callable[..., Item],
) -> None:
    """Previews reject bad parents too, not only applies."""
    with pytest.raises(HierarchyError):
        preview_reparent(store, tree["batch"].id, None)
    with pytest.raises(HierarchyError):
        preview_reparent(store, tree["open"].id, None)
    with pytest.raises(HierarchyError):
        preview_reparent(store, tree["batch"].id, tree["open"].id)
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        preview_reparent(store, tree["batch"].id, foreign.id)
