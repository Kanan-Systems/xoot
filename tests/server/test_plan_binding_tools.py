"""End to end: tokens bind the previewed plan; drops keep the requested state."""

from collections.abc import Callable
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.confirm_service import PLAN_CHANGED
from xoot.services.item_service import get_item
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store


@pytest.fixture(name="parent")
def fixture_parent(
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> dict[str, Any]:
    """goal > batch, and an open session key."""
    goal = make_item(project, ItemKind.GOAL)
    return {
        "goal": goal,
        "batch": make_item(project, ItemKind.BATCH, parent_id=goal.id),
        "session": f"xoot-S{make_session(project).number}",
    }


def _drop(parent: dict[str, Any], state: str) -> dict[str, Any]:
    return {
        "session": parent["session"],
        "key": parent["goal"].key,
        "expected_version": parent["goal"].version,
        "changes": {"state": state},
    }


def test_drop_refused_after_a_child_is_added(
    store: Store,
    parent: dict[str, Any],
    row_counts: Callable[[], dict[str, int]],
    harness: Any,
) -> None:
    """A child added between preview and apply refuses the apply; nothing is written."""
    drop = _drop(parent, "dropped")

    async def scenario(client: ClientSession) -> dict[str, Any]:
        preview = await harness.ok(client, "item_update", **drop)
        await harness.ok(
            client,
            "item_create",
            session=parent["session"],
            kind="subtask",
            title="late child",
            parent=parent["batch"].key,
        )
        before = row_counts()
        error = await harness.error(
            client, "item_update", **drop, confirm_token=preview["confirm_token"]
        )
        return {"preview": preview, "error": error, "before": before}

    out = harness.run(scenario)
    assert out["preview"]["phase"] == "preview"
    assert PLAN_CHANGED in out["error"]
    assert row_counts() == out["before"]
    with store.read() as conn:
        used = conn.execute("SELECT used_at FROM confirm_token").fetchall()
    assert [row["used_at"] for row in used] == [None]
    assert get_item(store, parent["goal"].id).state == "open"


def test_item_update_drops_into_the_requested_state(
    store: Store,
    project: Project,
    ctx: WriteContext,
    parent: dict[str, Any],
    harness: Any,
) -> None:
    """A custom dropped state on a parent reaches the whole subtree through the tool."""
    data = WorkflowDefinition.default().model_dump(mode="json")
    for kind in ItemKind:
        data["kinds"][kind.value]["states"].append(
            {"name": "abandoned", "category": "dropped"}
        )
    change = WorkflowChange(definition=WorkflowDefinition.model_validate(data))
    set_workflow(store, project.id, change, ctx)
    drop = _drop(parent, "abandoned")

    async def scenario(client: ClientSession) -> dict[str, Any]:
        preview = await harness.ok(client, "item_update", **drop)
        token = preview["confirm_token"]
        applied = await harness.ok(client, "item_update", **drop, confirm_token=token)
        return {"preview": preview, "applied": applied}

    out = harness.run(scenario)
    for phase in ("preview", "applied"):
        assert out[phase]["mode"] == "drop"
        states = [c["after"]["state"] for c in out[phase]["plan"]["changes"]]
        assert states == ["abandoned", "abandoned"]
    items = (parent["goal"], parent["batch"])
    assert [get_item(store, i.id).state for i in items] == ["abandoned"] * 2
