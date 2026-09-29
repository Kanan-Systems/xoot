"""
The completion engine: goals and batches complete and reopen on their own.

Every write reports what it completed, reopened, or left blocked by open
backlog; those writes are the system's, in the same transaction.
"""

from collections.abc import Callable

from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.services.backlog_push_service import apply_push
from xoot.services.backlog_service import capture
from xoot.services.item_service import create_item, update_item
from xoot.services.lookups import require_item
from xoot.store.store import Store

type Tree = tuple[Item, Item, Item, Item]


def _state(store: Store, item: Item) -> str:
    with store.read() as conn:
        return require_item(conn, item.id).state


def _close(store: Store, ctx: WriteContext, item: Item, state: str) -> object:
    with store.read() as conn:
        version = require_item(conn, item.id).version
    return update_item(store, item.id, version, ItemUpdate(state=state), ctx)[1]


def test_batch_and_goal_complete_when_every_subtask_is_done(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """The last done subtask completes its batch, then the goal above it."""
    goal, batch, first, second = work_tree
    report = _close(store, ctx, first, "done")
    assert report.completed == () and _state(store, batch) == "open"
    report = _close(store, ctx, second, "done")
    assert report.completed == (batch.key, goal.key)
    assert report.reopened == () and report.blocked == ()
    assert (_state(store, batch), _state(store, goal)) == ("done", "done")


def test_all_dropped_drops_the_batch(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """When every child was dropped the parent takes its dropped state."""
    goal, batch, first, second = work_tree
    _close(store, ctx, first, "dropped")
    report = _close(store, ctx, second, "dropped")
    assert report.completed == (batch.key, goal.key)
    assert (_state(store, batch), _state(store, goal)) == ("dropped", "dropped")


def test_mixed_done_and_dropped_is_done(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """One done child is enough for done."""
    _, batch, first, second = work_tree
    _close(store, ctx, first, "dropped")
    _close(store, ctx, second, "done")
    assert _state(store, batch) == "done"


def test_open_backlog_blocks_and_is_reported(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """Nothing changes while open backlog sits on the batch; the write says so."""
    goal, batch, first, second = work_tree
    capture_on(first)
    _close(store, ctx, first, "done")
    report = _close(store, ctx, second, "done")
    assert report.completed == ()
    assert report.blocked == (BlockedItem(key=batch.key, open_backlog=1),)
    assert (_state(store, batch), _state(store, goal)) == ("open", "open")


def test_goal_backlog_blocks_the_goal_only(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """Backlog on the goal lets the batch complete but holds the goal."""
    goal, batch, first, second = work_tree
    capture_on(goal)
    _close(store, ctx, first, "done")
    report = _close(store, ctx, second, "done")
    assert report.completed == (batch.key,)
    assert report.blocked == (BlockedItem(key=goal.key, open_backlog=1),)
    assert _state(store, goal) == "open"


def test_new_subtask_reopens_a_done_batch_and_goal(
    store: Store, ctx: WriteContext, project: Project, work_tree: Tree
) -> None:
    """Creating a subtask in a done batch reopens it and its done goal."""
    goal, batch, first, second = work_tree
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    request = ItemCreate(kind=ItemKind.SUBTASK, title="more", parent_id=batch.id)
    _, report = create_item(store, project.id, request, ctx)
    assert report.reopened == (batch.key, goal.key)
    assert (_state(store, batch), _state(store, goal)) == ("open", "open")


def test_reopening_a_subtask_reopens_its_parents(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """A done subtask moved back to open reopens the batch and goal."""
    goal, batch, first, second = work_tree
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    report = _close(store, ctx, first, "active")
    assert report.reopened == (batch.key, goal.key)
    assert _state(store, batch) == "open"


def test_capture_reopens_a_done_batch_and_goal(
    store: Store, ctx: WriteContext, project: Project, work_tree: Tree
) -> None:
    """New open backlog on a done batch reopens it, and its goal."""
    goal, batch, first, second = work_tree
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    draft = ItemDraft(title="found", body="why")
    _, report = capture(store, project.id, first.id, draft, ctx)
    assert report.reopened == (batch.key, goal.key)


def test_goal_cascades_across_batches(
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
) -> None:
    """A goal completes only when its last open batch completes."""
    goal, batch, first, second = work_tree
    other = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    last = make_item(project, ItemKind.SUBTASK, parent_id=other.id)
    _close(store, ctx, first, "done")
    report = _close(store, ctx, second, "done")
    assert report.completed == (batch.key,)
    assert _state(store, goal) == "open"
    report = _close(store, ctx, last, "done")
    assert report.completed == (other.key, goal.key)


def test_no_children_never_completes(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """An empty batch, or a goal with only an empty batch, stays open."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    report = _close(store, ctx, batch, "active")
    assert report.completed == ()
    assert (_state(store, goal), _state(store, batch)) == ("open", "active")


def test_engine_writes_are_the_systems(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """The completion events carry the system actor and the caller's client."""
    _, batch, first, second = work_tree
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    with store.read() as conn:
        events = event_db.list_for_entity(conn, EntityType.ITEM, batch.id)
    last = events[-1]
    assert (last.actor_kind.value, last.client.value) == ("system", "cli")
    assert last.after is not None and last.after["state"] == "done"


def test_resolving_batch_backlog_directly_unblocks(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """item_update of a batch backlog item to done completes the waiting batch."""
    goal, batch, first, second = work_tree
    backlog = capture_on(first)
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    report = _close(store, ctx, backlog, "done")
    assert report.completed == (batch.key, goal.key)
    assert _state(store, backlog) == "done"


def test_resolving_goal_backlog_directly_unblocks(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """Resolving the goal's own backlog lets the goal complete."""
    goal, _, first, second = work_tree
    backlog = capture_on(goal)
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    report = _close(store, ctx, backlog, "done")
    assert report.completed == (goal.key,)


def test_resolving_project_backlog_directly(
    store: Store,
    ctx: WriteContext,
    work_tree: Tree,
    capture_on: Callable[..., Item],
) -> None:
    """
    A goal's only open backlog is pushed to the project and the goal
    completes; the project-level item then resolves directly to done.
    """
    goal, batch, first, second = work_tree
    on_goal = capture_on(goal)
    _close(store, ctx, first, "done")
    _close(store, ctx, second, "done")
    assert _state(store, goal) == "open"
    plan, report = apply_push(store, on_goal.id, ctx, None)
    assert plan.changes[0].after["key"] == "backlog-1"
    assert report.completed == (goal.key,)
    with store.read() as conn:
        on_project = require_item(conn, on_goal.id)
    report = _close(store, ctx, on_project, "done")
    assert report.completed == () and report.reopened == ()
    assert _state(store, on_project) == "done"
    assert _state(store, batch) == "done"
