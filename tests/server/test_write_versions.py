"""
Write results list every item whose version the call changed, the goals and
batches the completion engine wrote included, so the next call can pass
their expected_version; a push preview shows the number the item takes.
"""

from typing import Any

import pytest
from mcp import ClientSession

P = {"project": "xo"}
BULK = {
    **P,
    "items": [
        {
            "kind": "goal",
            "title": "export",
            "children": [
                {
                    "kind": "batch",
                    "title": "writer",
                    "children": [{"kind": "subtask", "title": "rows"}],
                }
            ],
        }
    ],
}


async def _bulk(client: ClientSession, harness: Any) -> None:
    preview = await harness.ok(client, "items_create_bulk", **BULK)
    await harness.ok(
        client, "items_create_bulk", **BULK, confirm_token=preview["confirm_token"]
    )


@pytest.mark.usefixtures("project")
def test_completion_writes_are_listed_and_usable(harness: Any) -> None:
    """Closing the last subtask lists the subtask, its batch and its goal."""

    async def scenario(client: ClientSession) -> tuple[Any, Any]:
        await _bulk(client, harness)
        done = await harness.ok(
            client, "item_update", **P, key="goal-1/batch-1/subtask-1",
            expected_version=1, changes={"state": "done"},
        )  # fmt: skip
        versions = {c["key"]: c["version"] for c in done["changed"]}
        renamed = await harness.ok(
            client, "item_update", **P, key="goal-1",
            expected_version=versions["goal-1"], changes={"title": "export v2"},
        )  # fmt: skip
        return done, renamed

    done, renamed = harness.run(scenario)
    assert done["completed"] == ["goal-1/batch-1", "goal-1"]
    assert done["changed"] == [
        {"key": "goal-1/batch-1/subtask-1", "version": 2, "state": "done"},
        {"key": "goal-1/batch-1", "version": 2, "state": "done"},
        {"key": "goal-1", "version": 2, "state": "done"},
    ]
    assert renamed["item"]["version"] == 3
    assert renamed["changed"] == [{"key": "goal-1", "version": 3, "state": "done"}]


@pytest.mark.usefixtures("project")
def test_capture_lists_the_reopened_batch(harness: Any) -> None:
    """A capture on a done batch reopens it; both writes are listed."""

    async def scenario(client: ClientSession) -> Any:
        await _bulk(client, harness)
        await harness.ok(
            client, "item_update", **P, key="goal-1/batch-1/subtask-1",
            expected_version=1, changes={"state": "done"},
        )  # fmt: skip
        return await harness.ok(
            client, "capture", **P, found_on="goal-1/batch-1", title="bom",
            body="found",
        )  # fmt: skip

    captured = harness.run(scenario)
    assert captured["reopened"] == ["goal-1/batch-1", "goal-1"]
    assert [(c["key"], c["version"]) for c in captured["changed"]] == [
        ("goal-1/batch-1/backlog-1", 1),
        ("goal-1/batch-1", 3),
        ("goal-1", 3),
    ]


@pytest.mark.usefixtures("project")
def test_push_preview_shows_the_new_number(harness: Any) -> None:
    """The preview's change carries the number next to the key."""

    async def scenario(client: ClientSession) -> Any:
        await _bulk(client, harness)
        await harness.ok(client, "capture", **P, found_on="goal-1", title="a", body="b")
        return await harness.ok(client, "backlog_push", **P, key="goal-1/backlog-1")

    preview = harness.run(scenario)
    (change,) = preview["plan"]["changes"]
    assert change["key"] == "goal-1/backlog-1"
    assert change["before"]["number"] == 1
    assert change["after"]["number"] == 1
    assert change["after"]["key"] == "backlog-1"
    assert change["after"]["parent"] is None
