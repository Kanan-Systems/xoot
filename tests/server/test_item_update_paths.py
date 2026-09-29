"""item_update picks a direct, drop or reparent path, and refuses mixed changes."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project


def _update(key: str, version: int, **changes: Any) -> dict[str, Any]:
    return {
        "project": "xo",
        "key": key,
        "expected_version": version,
        "changes": changes,
    }


def test_paths_and_mixed_change_rejection(
    project: Project,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
    harness: Any,
) -> None:
    """Childless moves and drops apply at once; mixing a move or drop is refused."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    leaf = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    other_goal = make_item(project, ItemKind.GOAL)
    other_batch = make_item(project, ItemKind.BATCH, parent_id=other_goal.id)
    backlog = capture_on(leaf)

    async def scenario(client: ClientSession) -> dict[str, Any]:
        return {
            "mixed_parent": await harness.error(
                client,
                "item_update",
                **_update(batch.key, 1, parent=other_goal.key, title="x"),
            ),
            "mixed_drop": await harness.error(
                client,
                "item_update",
                **_update(goal.key, 1, state="dropped", title="x"),
            ),
            "backlog_parent": await harness.error(
                client, "item_update", **_update(backlog.key, 1, parent=goal.key)
            ),
            "move_leaf": await harness.ok(
                client, "item_update", **_update(leaf.key, 1, parent=other_batch.key)
            ),
            "old_key": await harness.ok(client, "item_get", project="xo", key=leaf.key),
        }

    out = harness.run(scenario)
    assert "parent must be the only field" in out["mixed_parent"]
    assert "a drop of an item with children must be the only field" in out["mixed_drop"]
    assert "backlog_push or backlog_cover" in out["backlog_parent"]
    moved = out["move_leaf"]
    assert (moved["mode"], moved["phase"], moved["confirm_token"]) == (
        "reparent",
        "applied",
        None,
    )
    # A move shows the number the item takes under its new parent.
    assert moved["plan"]["changes"][0]["after"] == {
        "parent": other_batch.key,
        "number": 1,
        "key": "goal-2/batch-1/subtask-1",
    }
    assert out["old_key"]["item"]["key"] == "goal-2/batch-1/subtask-1"
    assert out["old_key"]["item"]["aliases"] == [leaf.key]


def _affected(output: dict[str, Any]) -> list[tuple[str, str, str | None, int]]:
    return [
        (entry["key"], entry["state"], entry["parent"], entry["version"])
        for entry in output["items"]
    ]


def test_applied_subtree_drop_returns_every_affected_item(
    project: Project,
    make_item: Callable[..., Item],
    harness: Any,
) -> None:
    """The drop returns each dropped item, deepest first, and completes nothing."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    args = _update(goal.key, 1, state="dropped")

    async def scenario(client: ClientSession) -> dict[str, Any]:
        preview = await harness.ok(client, "item_update", **args)
        applied = await harness.ok(
            client, "item_update", **args, confirm_token=preview["confirm_token"]
        )
        return {"preview": preview, "applied": applied}

    out = harness.run(scenario)
    assert out["preview"]["items"] is None
    assert out["applied"]["item"] is None
    assert _affected(out["applied"]) == [
        (subtask.key, "dropped", batch.key, 2),
        (batch.key, "dropped", goal.key, 2),
        (goal.key, "dropped", None, 2),
    ]
    assert out["applied"]["completed"] == []


def test_applied_subtree_reparent_returns_every_affected_item(
    project: Project,
    make_item: Callable[..., Item],
    harness: Any,
) -> None:
    """The moved root and its re-keyed descendants, as they now stand."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    other_goal = make_item(project, ItemKind.GOAL)
    args = _update(batch.key, 1, parent=other_goal.key)

    async def scenario(client: ClientSession) -> dict[str, Any]:
        preview = await harness.ok(client, "item_update", **args)
        return await harness.ok(
            client, "item_update", **args, confirm_token=preview["confirm_token"]
        )

    out = harness.run(scenario)
    assert out["item"] is None
    assert _affected(out) == [
        ("goal-2/batch-1", "open", "goal-2", 2),
        ("goal-2/batch-1/subtask-1", "open", "goal-2/batch-1", 2),
    ]
