"""Service side: workflow changes remap items or are refused whole."""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.exceptions.state_error import StateError
from xoot.exceptions.workflow_mapping_error import WorkflowMappingError
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.item_service import capture, get_item, update_item
from xoot.services.project_service import get_project
from xoot.services.workflow_service import get_active_workflow, set_workflow
from xoot.store.store import Store


def _definition(kind: ItemKind, **overrides: Any) -> WorkflowDefinition:
    """The default definition with one kind's workflow fields replaced."""
    data = WorkflowDefinition.default().model_dump(mode="json")
    data["kinds"][kind.value].update(overrides)
    return WorkflowDefinition.model_validate(data)


def _without(kind: ItemKind, removed: str) -> WorkflowDefinition:
    states = (
        WorkflowDefinition.default().for_kind(kind).model_dump(mode="json")["states"]
    )
    return _definition(kind, states=[s for s in states if s["name"] != removed])


def test_removing_an_in_use_state_needs_a_mapping(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Without a mapping the change is refused and nothing is written."""
    make_item(project, ItemKind.SUBTASK, state="blocked")
    before = row_counts()
    change = WorkflowChange(definition=_without(ItemKind.SUBTASK, "blocked"))
    with pytest.raises(WorkflowMappingError, match="subtask:blocked"):
        set_workflow(store, project.id, change, ctx)
    assert row_counts() == before


def test_mapping_remaps_items(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
    event_kinds: Callable[[Project], list[tuple[str, str]]],
) -> None:
    """Items in a removed state move to the mapped state, with events."""
    blocked = make_item(project, ItemKind.SUBTASK, state="blocked")
    goal = make_item(project, ItemKind.GOAL, state="blocked")
    seen = len(event_kinds(project))
    change = WorkflowChange(
        definition=_without(ItemKind.SUBTASK, "blocked"),
        mapping={ItemKind.SUBTASK: {"blocked": "active"}},
    )
    workflow = set_workflow(store, project.id, change, ctx)
    assert workflow.version == 2
    assert get_project(store, project.id).active_workflow_id == workflow.id
    assert get_active_workflow(store, project.id) == workflow
    assert (get_item(store, blocked.id).state, get_item(store, blocked.id).version) == (
        "active",
        2,
    )
    assert get_item(store, goal.id) == goal
    assert event_kinds(project)[seen:] == [
        ("workflow", "create"),
        ("project", "update"),
        ("item", "update"),
    ]


@pytest.mark.parametrize("source", ["active", "someday"])
def test_mapping_may_only_name_removed_states(
    store: Store, project: Project, ctx: WriteContext, source: str
) -> None:
    """Mapping a kept or unknown state is refused."""
    change = WorkflowChange(
        definition=_without(ItemKind.SUBTASK, "blocked"),
        mapping={ItemKind.SUBTASK: {source: "open"}},
    )
    with pytest.raises(WorkflowMappingError, match="removes"):
        set_workflow(store, project.id, change, ctx)


def test_leaving_backlogged_category_clears_session_backlog(
    store: Store,
    project: Project,
    make_session: Callable[..., Session],
    user: Actor,
    ctx: WriteContext,
) -> None:
    """A remap out of the backlogged category clears the session backlog too."""
    item = capture(store, make_session(project).id, ItemDraft(title="idea"), user)
    default = WorkflowDefinition.default().for_kind(ItemKind.SUBTASK)
    states = [
        s.model_dump(mode="json") for s in default.states if s.name != "backlogged"
    ]
    definition = _definition(
        ItemKind.SUBTASK,
        states=[*states, {"name": "icebox", "category": "backlogged"}],
        defaults={"open": "open", "backlogged": "icebox", "dropped": "dropped"},
    )
    change = WorkflowChange(
        definition=definition, mapping={ItemKind.SUBTASK: {"backlogged": "open"}}
    )
    set_workflow(store, project.id, change, ctx)
    moved = get_item(store, item.id)
    assert (moved.state, moved.backlog_session_id) == ("open", None)


def test_transitions_apply_to_user_moves(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """Once a workflow restricts transitions, update_item enforces them."""
    goal = make_item(project, ItemKind.GOAL)
    definition = _definition(ItemKind.GOAL, transitions={"open": ["active"]})
    set_workflow(store, project.id, WorkflowChange(definition=definition), ctx)
    with pytest.raises(StateError, match="not allowed"):
        update_item(store, goal.id, 1, ItemUpdate(state="done"), ctx)
    assert (
        update_item(store, goal.id, 1, ItemUpdate(state="active"), ctx).state
        == "active"
    )


def test_identical_definition_is_a_no_op(
    store: Store,
    project: Project,
    ctx: WriteContext,
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Setting the active definition again adds no version and no event."""
    active = get_active_workflow(store, project.id)
    before = row_counts()
    change = WorkflowChange(definition=WorkflowDefinition.default())
    assert set_workflow(store, project.id, change, ctx) == active
    assert row_counts() == before
    assert get_project(store, project.id).active_workflow_id == active.id
