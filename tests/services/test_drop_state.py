"""Z3: a subtree drop honors a requested dropped state, or uses the default."""

from collections.abc import Callable, Iterable

import pytest

from xoot.exceptions.state_error import StateError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.item_service import get_item
from xoot.services.subtree_service import apply_drop, preview_drop
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store

EXTRA = "abandoned"


def with_extra_dropped(kinds: Iterable[ItemKind]) -> WorkflowDefinition:
    """
    The default workflow plus a second dropped state for some kinds.

    Args:
        - kinds (Iterable[ItemKind]): the kinds that get the extra state.

    Returns:
        - definition (WorkflowDefinition): the extended definition.
    """
    data = WorkflowDefinition.default().model_dump(mode="json")
    for kind in kinds:
        data["kinds"][kind.value]["states"].append(
            {"name": EXTRA, "category": Category.DROPPED.value}
        )
    return WorkflowDefinition.model_validate(data)


@pytest.fixture(name="subtree")
def fixture_subtree(
    project: Project, make_item: Callable[..., Item]
) -> tuple[Item, Item, Item]:
    """goal > batch > subtask, all open."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    return goal, batch, make_item(project, ItemKind.SUBTASK, parent_id=batch.id)


def _states(store: Store, items: Iterable[Item]) -> list[str]:
    return [get_item(store, item.id).state for item in items]


def test_requested_dropped_state_is_honored(
    store: Store,
    project: Project,
    ctx: WriteContext,
    subtree: tuple[Item, Item, Item],
) -> None:
    """Preview and apply both use the requested state for every item."""
    set_workflow(
        store, project.id, WorkflowChange(definition=with_extra_dropped(ItemKind)), ctx
    )
    goal = subtree[0]
    preview = preview_drop(store, goal.id, EXTRA)
    assert [c.after["state"] for c in preview.changes] == [EXTRA] * 3
    assert apply_drop(store, goal.id, goal.version, ctx, state=EXTRA) == preview
    assert _states(store, subtree) == [EXTRA] * 3


def test_no_requested_state_uses_the_default(
    store: Store,
    project: Project,
    ctx: WriteContext,
    subtree: tuple[Item, Item, Item],
) -> None:
    """Without a request each kind's default dropped state is used."""
    set_workflow(
        store, project.id, WorkflowChange(definition=with_extra_dropped(ItemKind)), ctx
    )
    goal = subtree[0]
    apply_drop(store, goal.id, goal.version, ctx)
    assert _states(store, subtree) == ["dropped"] * 3


@pytest.mark.parametrize("state", ["active", "backlogged", "no-such-state"])
def test_state_outside_the_dropped_category_is_refused(
    store: Store,
    ctx: WriteContext,
    subtree: tuple[Item, Item, Item],
    row_counts: Callable[[], dict[str, int]],
    state: str,
) -> None:
    """A non-dropped or unknown state fails the preview and the apply, writing nothing."""
    goal = subtree[0]
    before = row_counts()
    with pytest.raises(StateError, match="not a dropped state"):
        preview_drop(store, goal.id, state)
    with pytest.raises(StateError, match="not a dropped state"):
        apply_drop(store, goal.id, goal.version, ctx, state=state)
    assert row_counts() == before
    assert _states(store, subtree) == ["open"] * 3


def test_kind_without_the_state_takes_its_default(
    store: Store,
    project: Project,
    ctx: WriteContext,
    subtree: tuple[Item, Item, Item],
) -> None:
    """The request is checked on the root's kind; other kinds fall back to their default."""
    definition = with_extra_dropped([ItemKind.GOAL])
    set_workflow(store, project.id, WorkflowChange(definition=definition), ctx)
    goal = subtree[0]
    apply_drop(store, goal.id, goal.version, ctx, state=EXTRA)
    assert _states(store, subtree) == [EXTRA, "dropped", "dropped"]
