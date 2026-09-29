"""plan_workflow_change previews set_workflow: removed states and remap counts."""

from collections.abc import Callable

import pytest

from xoot.exceptions.workflow_mapping_error import WorkflowMappingError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.workflow_service import plan_workflow_change, set_workflow
from xoot.store.store import Store


def _without_blocked() -> WorkflowDefinition:
    default = WorkflowDefinition.default()
    goal = default.for_kind(ItemKind.GOAL)
    states = tuple(s for s in goal.states if s.category is not Category.BLOCKED)
    kinds = dict(default.kinds)
    kinds[ItemKind.GOAL] = KindWorkflow(states=states, defaults=goal.defaults)
    return WorkflowDefinition(kinds=kinds)


def test_plan_counts_and_writes_nothing(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Two blocked goals would move; the plan says so and changes no row."""
    for _ in range(2):
        make_item(project, ItemKind.GOAL, state="blocked")
    make_item(project, ItemKind.GOAL)
    change = WorkflowChange(
        definition=_without_blocked(), mapping={ItemKind.GOAL: {"blocked": "open"}}
    )
    before = row_counts()
    plan = plan_workflow_change(store, project.id, change)
    assert row_counts() == before
    assert plan.removed == {
        ItemKind.GOAL: ("blocked",),
        ItemKind.BATCH: (),
        ItemKind.SUBTASK: (),
        ItemKind.BACKLOG: (),
    }
    assert plan.remaps == {
        ItemKind.GOAL: 2,
        ItemKind.BATCH: 0,
        ItemKind.SUBTASK: 0,
        ItemKind.BACKLOG: 0,
    }
    assert set_workflow(store, project.id, change, ctx).version == 2


def test_plan_refuses_a_missing_mapping(
    store: Store, project: Project, make_item: Callable[..., Item]
) -> None:
    """The same refusal set_workflow would give, before any prompt."""
    make_item(project, ItemKind.GOAL, state="blocked")
    change = WorkflowChange(definition=_without_blocked())
    with pytest.raises(WorkflowMappingError):
        plan_workflow_change(store, project.id, change)
