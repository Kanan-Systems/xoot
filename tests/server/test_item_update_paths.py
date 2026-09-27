"""E11: item_update picks a direct, drop or reparent path, and refuses mixed changes."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session


def test_paths_and_mixed_change_rejection(
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
    harness: Any,
) -> None:
    """Childless moves and drops apply at once; mixing a move or drop is refused."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    other_goal = make_item(project, ItemKind.GOAL)
    loose = make_item(project, ItemKind.SUBTASK)
    make_session(project)

    def update(key: str, version: int, **changes: Any) -> dict[str, Any]:
        return {
            "session": "xoot-S1",
            "key": key,
            "expected_version": version,
            "changes": changes,
        }

    async def scenario(client: ClientSession) -> dict[str, Any]:
        call = client.call_tool
        return {
            "mixed_parent": await harness.error(
                client,
                "item_update",
                **update(batch.key, 1, parent=other_goal.key, title="x"),
            ),
            "mixed_drop": await harness.error(
                client, "item_update", **update(goal.key, 1, state="dropped", title="x")
            ),
            "file_loose": await harness.ok(
                client, "item_update", **update(loose.key, 1, parent=batch.key)
            ),
            "drop_leaf": await harness.ok(
                client, "item_update", **update(other_goal.key, 1, state="dropped")
            ),
            "untouched": (
                await call("item_get", {"key": batch.key})
            ).structured_content,
        }

    out = harness.run(scenario)
    assert "parent must be the only field" in out["mixed_parent"]
    assert "a drop of an item with children must be the only field" in out["mixed_drop"]
    assert (out["file_loose"]["mode"], out["file_loose"]["phase"]) == (
        "reparent",
        "applied",
    )
    assert out["file_loose"]["confirm_token"] is None
    assert out["file_loose"]["plan"]["changes"][0]["after"] == {"parent": batch.key}
    assert (out["drop_leaf"]["mode"], out["drop_leaf"]["phase"]) == (
        "update",
        "applied",
    )
    assert out["drop_leaf"]["item"]["state"] == "dropped"
    assert out["untouched"]["item"]["version"] == 1
