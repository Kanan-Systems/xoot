"""GET /workflow lists every item kind's states and categories."""

from typing import Any

from starlette.testclient import TestClient

from xoot.exceptions.state_error import StateError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.item_rules import check_transition
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store


def test_every_kind_lists_its_states_in_order(client: TestClient, seeded: Any) -> None:
    """States come in workflow order with their categories, as brief_get shows them."""
    assert seeded.goal.key == "goal-1"
    response = client.get("/api/v1/projects/xoot/workflow")
    assert response.status_code == 200
    default = WorkflowDefinition.default()
    assert response.json() == {
        "workflow": {
            str(kind): {
                "states": [
                    {"name": state.name, "category": str(state.category)}
                    for state in workflow.states
                ],
                "transitions_restricted": False,
                "transitions": None,
            }
            for kind, workflow in default.kinds.items()
        }
    }


def test_it_matches_the_brief(client: TestClient, seeded: Any) -> None:
    """The same states and flags brief_get and the brief route carry."""
    assert seeded.goal.key == "goal-1"
    brief = client.get("/api/v1/projects/xoot/brief").json()
    workflow = client.get("/api/v1/projects/xoot/workflow").json()
    assert {
        kind: {name: value for name, value in entry.items() if name != "transitions"}
        for kind, entry in workflow["workflow"].items()
    } == brief["workflow"]


def test_an_unknown_project_or_a_query_is_refused(client: TestClient) -> None:
    """404 for a prefix that names nothing; 400 for any query parameter."""
    assert client.get("/api/v1/projects/nope/workflow").status_code == 404
    assert client.get("/api/v1/projects/xoot/workflow?x=1").status_code == 400


def _restrict(store: Store, project: Project, ctx: WriteContext) -> KindWorkflow:
    """Restrict goals: open -> active, active -> done or open, done listed empty;
    every other goal state is absent from the table, so it moves nowhere."""
    data = WorkflowDefinition.default().model_dump(mode="json")
    data["kinds"]["goal"]["transitions"] = {
        "open": ["active"],
        "active": ["done", "open"],
        "done": [],
    }
    definition = WorkflowDefinition.model_validate(data)
    set_workflow(store, project.id, WorkflowChange(definition=definition), ctx)
    return definition.for_kind(ItemKind.GOAL)


def test_a_restricted_kind_maps_every_state_to_its_moves(
    client: TestClient, store: Store, project: Project, ctx: WriteContext
) -> None:
    """Every state is a key, in workflow order; unlisted and empty states map to []."""
    _restrict(store, project, ctx)
    goal = client.get("/api/v1/projects/xoot/workflow").json()["workflow"]["goal"]
    assert goal["transitions_restricted"] is True
    assert goal["transitions"] == {
        "open": ["active"],
        "active": ["open", "done"],
        "blocked": [],
        "awaiting_input": [],
        "done": [],
        "dropped": [],
    }
    others = client.get("/api/v1/projects/xoot/workflow").json()["workflow"]
    assert all(
        others[kind]["transitions"] is None for kind in ("batch", "subtask", "backlog")
    )


def test_the_map_agrees_with_check_transition_on_every_pair(
    client: TestClient, store: Store, project: Project, ctx: WriteContext
) -> None:
    """For each pair of distinct states, listed exactly when the service allows it."""
    workflow = _restrict(store, project, ctx)
    moves = client.get("/api/v1/projects/xoot/workflow").json()["workflow"]["goal"][
        "transitions"
    ]
    names = [spec.name for spec in workflow.states]
    for source in names:
        for target in names:
            try:
                check_transition(workflow, source, target)
                allowed = True
            except StateError:
                allowed = False
            if source == target:
                assert allowed and target not in moves[source]
            else:
                assert (target in moves[source]) is allowed, (source, target)
