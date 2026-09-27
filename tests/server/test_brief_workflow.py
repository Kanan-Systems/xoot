"""Z1: brief_get shows the active workflow, so clients use real state names."""

from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.server.brief import build_brief
from xoot.services.project_service import get_project
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store


@pytest.mark.usefixtures("project")
def test_brief_lists_every_default_state(harness: Any) -> None:
    """Every state of the default workflow, per kind, with its category."""

    async def scenario(client: ClientSession) -> Any:
        return await harness.ok(client, "brief_get", project="xo")

    workflow = harness.run(scenario)["workflow"]
    default = WorkflowDefinition.default()
    assert set(workflow) == {kind.value for kind in ItemKind}
    for kind in ItemKind:
        expected = [
            {"name": spec.name, "category": spec.category.value}
            for spec in default.for_kind(kind).states
        ]
        assert workflow[kind.value]["states"] == expected
        assert workflow[kind.value]["transitions_restricted"] is False


def test_brief_flags_restricted_transitions(
    store: Store, project: Project, ctx: WriteContext
) -> None:
    """A kind with a transitions map is reported as restricted; the others are not."""
    data = WorkflowDefinition.default().model_dump(mode="json")
    data["kinds"]["goal"]["transitions"] = {"open": ["active"]}
    change = WorkflowChange(definition=WorkflowDefinition.model_validate(data))
    set_workflow(store, project.id, change, ctx)
    current = get_project(store, project.id)
    with store.read() as conn:
        brief = build_brief(conn, current, "alias", store.path)
    assert brief.workflow[ItemKind.GOAL].transitions_restricted is True
    assert brief.workflow[ItemKind.BATCH].transitions_restricted is False
