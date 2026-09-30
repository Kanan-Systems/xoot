"""capture placement, backlog_cover, and backlog reads."""

from collections.abc import Callable

import pytest

from xoot.exceptions.backlog_error import BacklogError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.backlog_push_service import apply_push
from xoot.services.backlog_reads import (
    backlog_counts,
    backlog_items,
    backlog_level,
    blocked_items,
)
from xoot.services.backlog_service import cover
from xoot.services.lookups import require_item
from xoot.store.store import Store

type Tree = tuple[Item, Item, Item, Item]


def _pushed_to_project(store: Store, ctx: WriteContext, item: Item) -> Item:
    """Push a goal-level item to the project and return its new row."""
    apply_push(store, item.id, ctx, None)
    with store.read() as conn:
        return require_item(conn, item.id)


def test_capture_on_a_subtask_lands_on_its_batch(
    work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """found_on a subtask: the backlog item sits on the subtask's batch."""
    _, batch, first, _ = work_tree
    item = capture_on(first, "idea", "because")
    assert (item.kind, item.parent_id, item.found_on_item_id) == (
        ItemKind.BACKLOG,
        batch.id,
        first.id,
    )
    assert (item.key, item.state, item.body) == (
        "goal-1/batch-1/backlog-1",
        "open",
        "because",
    )


def test_capture_on_a_batch_or_goal_lands_on_it(
    work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """found_on a batch or a goal: the item sits right on it."""
    goal, batch, _, _ = work_tree
    assert capture_on(batch).parent_id == batch.id
    assert capture_on(goal).parent_id == goal.id


def test_capture_on_a_backlog_item_lands_beside_it(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """found_on a backlog item: same level, the project for a project-level one."""
    goal, _, first, _ = work_tree
    on_batch = capture_on(first)
    assert capture_on(on_batch).parent_id == on_batch.parent_id
    on_project = _pushed_to_project(store, ctx, capture_on(goal))
    beside = capture_on(on_project)
    assert (beside.parent_id, beside.key) == (None, "backlog-2")
    assert beside.found_on_item_id == on_project.id


def test_cover_in_its_own_batch(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """The subtask copies title and body; the links go both ways; item done."""
    _, batch, first, _ = work_tree
    backlog = capture_on(first, "handle BOM", "Excel adds one")
    subtask, closed, _ = cover(store, backlog.id, None, ctx)
    assert (subtask.parent_id, subtask.key) == (batch.id, "goal-1/batch-1/subtask-3")
    assert (subtask.title, subtask.body) == ("handle BOM", "Excel adds one")
    assert subtask.origin_item_id == backlog.id
    assert (closed.state, closed.covered_by_item_id) == ("done", subtask.id)


# Each fixture the test needs is one argument.
def test_cover_in_a_named_batch_of_the_same_goal(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """A batch item may be covered in another batch of its goal."""
    goal, _, first, _ = work_tree
    other = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask, _, _ = cover(store, capture_on(first).id, other.id, ctx)
    assert subtask.key == "goal-1/batch-2/subtask-1"


# Each fixture the test needs is one argument.
def test_goal_level_cover_requires_a_batch_of_that_goal(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """No batch: refused. A batch of another goal: refused. Its own: covered."""
    goal, batch, _, _ = work_tree
    backlog = capture_on(goal)
    with pytest.raises(BacklogError, match="name the batch"):
        cover(store, backlog.id, None, ctx)
    elsewhere = make_item(
        project, ItemKind.BATCH, parent_id=make_item(project, ItemKind.GOAL).id
    )
    with pytest.raises(BacklogError, match="is not in goal goal-1"):
        cover(store, backlog.id, elsewhere.id, ctx)
    subtask, _, _ = cover(store, backlog.id, batch.id, ctx)
    assert subtask.parent_id == batch.id


# Each fixture the test needs is one argument.
def test_project_level_cover_goes_into_a_named_batch_of_any_goal(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """A project-level item needs a batch, from any goal; then it is a subtask."""
    goal, _, _, _ = work_tree
    item = _pushed_to_project(store, ctx, capture_on(goal))
    with pytest.raises(BacklogError, match="sits on the project"):
        cover(store, item.id, None, ctx)
    far = make_item(
        project, ItemKind.BATCH, parent_id=make_item(project, ItemKind.GOAL).id
    )
    subtask, closed, _ = cover(store, item.id, far.id, ctx)
    assert subtask.key == "goal-2/batch-1/subtask-1"
    assert (closed.state, closed.covered_by_item_id) == ("done", subtask.id)


def test_cover_refuses_non_batches_and_closed_items(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """Only an open backlog item can be covered, and only into a batch."""
    goal, _, first, _ = work_tree
    backlog = capture_on(first)
    with pytest.raises(BacklogError, match="is not a batch"):
        cover(store, backlog.id, goal.id, ctx)
    with pytest.raises(BacklogError, match="is not a backlog item"):
        cover(store, first.id, None, ctx)
    cover(store, backlog.id, None, ctx)
    with pytest.raises(BacklogError, match="already done or dropped"):
        cover(store, backlog.id, None, ctx)


def test_cover_completes_nothing_while_the_new_subtask_is_open(
    store: Store,
    ctx: WriteContext,
    work_tree: Tree,
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> None:
    """Covering swaps open backlog for an open subtask: the batch stays open."""
    _, batch, first, second = work_tree
    backlog = capture_on(first)
    set_state(first, "done")
    set_state(second, "done")
    subtask, _, report = cover(store, backlog.id, None, ctx)
    assert report.completed == () and report.blocked == ()
    set_state(subtask, "done")
    with store.read() as conn:
        assert require_item(conn, batch.id).state == "done"


# Each fixture the test needs is one argument.
def test_backlog_reads_by_level(  # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> None:
    """Listing, levels, counts per level and what open backlog blocks."""
    goal, batch, first, second = work_tree
    on_batch = capture_on(first)
    on_goal = capture_on(goal)
    on_project = _pushed_to_project(store, ctx, capture_on(goal))
    closed = capture_on(batch)
    set_state(closed, "dropped")
    set_state(first, "done")
    set_state(second, "done")
    with store.read() as conn:
        listed = backlog_items(conn, project.id)
        assert [i.key for i in listed] == [on_project.key, on_goal.key, on_batch.key]
        assert [backlog_level(i) for i in listed] == ["project", "goal", "batch"]
        assert [i.id for i in backlog_items(conn, project.id, batch)] == [on_batch.id]
        with_closed = backlog_items(conn, project.id, batch, include_closed=True)
        assert len(with_closed) == 2
        assert backlog_counts(conn, project.id) == {
            "project": 1,
            "goal": 1,
            "batch": 1,
        }
        assert blocked_items(conn, project.id) == [
            BlockedItem(key=batch.key, open_backlog=1)
        ]


def test_backlog_sorts_numbers_as_numbers(
    store: Store,
    ctx: WriteContext,
    project: Project,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """backlog-10 comes after backlog-2, and goal-10 after goal-2."""
    goals = [make_item(project, ItemKind.GOAL) for _ in range(10)]
    on_goals = [capture_on(goal) for goal in goals]
    on_project = [
        _pushed_to_project(store, ctx, capture_on(goals[0])) for _ in range(10)
    ]
    with store.read() as conn:
        keys = [i.key for i in backlog_items(conn, project.id)]
    assert keys == [i.key for i in on_project + on_goals]
    assert keys.index("backlog-2") < keys.index("backlog-10")
    assert keys.index("goal-2/backlog-1") < keys.index("goal-10/backlog-1")
