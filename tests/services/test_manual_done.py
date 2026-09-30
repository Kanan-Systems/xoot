"""A goal or batch cannot be set done by hand while work under it is open."""

from collections.abc import Callable

import pytest

from xoot.exceptions.open_children_error import KEYS_SHOWN, OpenChildrenError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.services.item_service import update_item
from xoot.services.lookups import require_item
from xoot.store.store import Store


def _current(store: Store, item: Item) -> Item:
    with store.read() as conn:
        return require_item(conn, item.id)


def _set(store: Store, ctx: WriteContext, item: Item, **changes: str) -> Item:
    current = _current(store, item)
    return update_item(store, item.id, current.version, ItemUpdate(**changes), ctx)[0]


def test_done_goal_with_an_open_batch_is_refused(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """The error names the open batch and nothing is written."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    with pytest.raises(OpenChildrenError, match=batch.key) as caught:
        _set(store, ctx, goal, state="done")
    assert caught.value.open_keys == (batch.key,)
    after = _current(store, goal)
    assert (after.state, after.version) == ("open", goal.version)


def test_done_batch_no_longer_completes_its_goal(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Before the guard, a hand-closed only batch completed the goal above it."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    with pytest.raises(OpenChildrenError, match=subtask.key):
        _set(store, ctx, batch, state="done")
    assert (_current(store, batch).state, _current(store, goal).state) == (
        "open",
        "open",
    )


def test_open_backlog_on_a_batch_blocks_a_manual_done(
    store: Store,
    ctx: WriteContext,
    project: Project,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> None:
    """Every child done, but an open backlog item on the batch: still refused."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    backlog = capture_on(subtask)
    _set(store, ctx, subtask, state="done")
    assert _current(store, batch).state == "open"
    with pytest.raises(OpenChildrenError) as caught:
        _set(store, ctx, batch, state="done")
    assert caught.value.open_keys == (backlog.key,)


def test_done_batch_with_every_child_closed_still_works(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """A batch reopened by hand over closed children can be closed by hand again."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="done")
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="dropped")
    _set(store, ctx, batch, state="active")
    assert _set(store, ctx, batch, state="done").state == "done"


def test_a_childless_batch_can_be_set_done(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """With nothing under it there is nothing to wait for."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    assert _set(store, ctx, batch, state="done").state == "done"


def test_other_changes_on_an_open_parent_are_unaffected(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Title changes and non-done states pass; only a done state is checked."""
    goal = make_item(project, ItemKind.GOAL)
    make_item(project, ItemKind.BATCH, parent_id=goal.id)
    assert _set(store, ctx, goal, title="renamed").title == "renamed"
    assert _set(store, ctx, goal, state="active").state == "active"


def test_the_listed_keys_are_capped(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Past KEYS_SHOWN keys the message says how many more there are."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtasks = [
        make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
        for _ in range(KEYS_SHOWN + 2)
    ]
    with pytest.raises(OpenChildrenError) as caught:
        _set(store, ctx, batch, state="done")
    message = str(caught.value)
    assert len(caught.value.open_keys) == KEYS_SHOWN + 2
    assert subtasks[KEYS_SHOWN - 1].key in message
    assert f"{subtasks[KEYS_SHOWN].key}," not in message
    assert message.count(f"{batch.key}/subtask-") == KEYS_SHOWN
    assert "and 2 more" in message


def test_automatic_completion_is_unaffected(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Closing the last subtask still completes the batch and the goal."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    _set(store, ctx, subtask, state="done")
    assert (_current(store, batch).state, _current(store, goal).state) == (
        "done",
        "done",
    )
