"""
All 15 tools end to end through stdio: a goal is planned, worked, blocked by
backlog, unblocked, completed and reopened, with decisions along the way.
Every write result carries completed, reopened and blocked.
"""

from typing import Any

from mcp import ClientSession

from xoot.models.project.project import Project
from xoot.store.store import Store

P = {"project": "xo"}


async def _flow(client: ClientSession, harness: Any) -> dict[str, Any]:
    """One scripted conversation touching every tool; returns what it saw."""
    ok = harness.ok
    seen: dict[str, Any] = {"projects": await ok(client, "projects_list")}
    bulk_args = {
        **P,
        "items": [
            {
                "kind": "goal",
                "title": "CSV export",
                "children": [
                    {
                        "kind": "batch",
                        "title": "Writer",
                        "children": [
                            {"kind": "subtask", "title": "quote cells"},
                            {"kind": "subtask", "title": "write rows"},
                        ],
                    }
                ],
            }
        ],
    }
    preview = await ok(client, "items_create_bulk", **bulk_args)
    seen["bulk_preview"] = preview
    seen["bulk"] = await ok(
        client, "items_create_bulk", **bulk_args, confirm_token=preview["confirm_token"]
    )
    seen["second_batch"] = await ok(
        client, "item_create", **P, kind="batch", title="Docs", parent="goal-1"
    )
    seen["docs_task"] = await ok(
        client, "item_create", **P, kind="subtask", title="readme",
        parent="goal-1/batch-2",
    )  # fmt: skip
    seen["capture"] = await ok(
        client, "capture", **P, found_on="goal-1/batch-1/subtask-1",
        title="handle BOM", body="Excel adds one",
    )  # fmt: skip
    seen["capture_goal"] = await ok(
        client, "capture", **P, found_on="goal-1", title="i18n", body="later"
    )
    seen["backlog"] = await ok(client, "backlog_list", **P)
    seen["backlog_at"] = await ok(client, "backlog_list", **P, at="goal-1/batch-1")
    for key in ("goal-1/batch-1/subtask-1", "goal-1/batch-1/subtask-2"):
        seen[f"done {key}"] = await ok(
            client, "item_update", **P, key=key, expected_version=1,
            changes={"state": "done"},
        )  # fmt: skip
    seen["brief_blocked"] = await ok(client, "brief_get", **P)
    seen["cover"] = await ok(
        client, "backlog_cover", **P, key="goal-1/batch-1/backlog-1"
    )
    seen["done_cover"] = await ok(
        client, "item_update", **P, key="goal-1/batch-1/subtask-3",
        expected_version=1, changes={"state": "done"},
    )  # fmt: skip
    push_preview = await ok(client, "backlog_push", **P, key="goal-1/backlog-1")
    seen["push_preview"] = push_preview
    seen["push"] = await ok(
        client, "backlog_push", **P, key="goal-1/backlog-1",
        confirm_token=push_preview["confirm_token"],
    )  # fmt: skip
    seen["done_docs"] = await ok(
        client, "item_update", **P, key="goal-1/batch-2/subtask-1",
        expected_version=1, changes={"state": "done"},
    )  # fmt: skip
    seen["decision"] = await ok(
        client, "decision_record", **P, owner="goal-1/batch-1",
        title="RFC 4180", body="quote everything",
    )  # fmt: skip
    seen["decision2"] = await ok(
        client, "decision_record", **P, owner="goal-1/batch-2/subtask-1",
        title="RFC 4180 minimal", body="quote when needed",
        supersedes="goal-1/batch-1/decision-1",
    )  # fmt: skip
    seen["decision_update"] = await ok(
        client, "decision_update", key="xoot:goal-1/batch-2/subtask-1/decision-1",
        expected_version=1, changes={"status": "deferred"},
    )  # fmt: skip
    seen["decisions"] = await ok(client, "decisions_list", **P)
    seen["decision_get"] = await ok(
        client, "decision_get", **P, key="goal-1/batch-1/decision-1"
    )
    seen["reopen"] = await ok(
        client, "item_create", **P, kind="subtask", title="more",
        parent="goal-1/batch-2",
    )  # fmt: skip
    seen["tree"] = await ok(client, "tree_get", **P, include_done=True, depth=3)
    seen["item"] = await ok(client, "item_get", **P, key="goal-1/batch-1")
    seen["pushed_old_key"] = await ok(client, "item_get", **P, key="goal-1/backlog-1")
    seen["brief"] = await ok(client, "brief_get", **P)
    return seen


def test_every_tool_in_one_goal(store: Store, project: Project, harness: Any) -> None:
    """The goal lifecycle through all 15 tools, with completion in the results."""

    async def scenario(client: ClientSession) -> dict[str, Any]:
        return await _flow(client, harness)

    seen = harness.run(scenario)
    assert [p["key_prefix"] for p in seen["projects"]["projects"]] == ["xoot"]
    assert [p["key"] for p in seen["bulk_preview"]["planned"]] == [
        "goal-1",
        "goal-1/batch-1",
        "goal-1/batch-1/subtask-1",
        "goal-1/batch-1/subtask-2",
    ]
    assert seen["bulk"]["phase"] == "applied"
    assert seen["docs_task"]["item"]["key"] == "goal-1/batch-2/subtask-1"
    captured = seen["capture"]["item"]
    assert (captured["key"], captured["found_on"]) == (
        "goal-1/batch-1/backlog-1",
        "goal-1/batch-1/subtask-1",
    )
    assert [i["level"] for i in seen["backlog"]["items"]] == ["goal", "batch"]
    assert [i["key"] for i in seen["backlog_at"]["items"]] == [captured["key"]]
    assert seen["done goal-1/batch-1/subtask-2"]["blocked"] == [
        {"key": "goal-1/batch-1", "open_backlog": 1}
    ]
    assert seen["brief_blocked"]["blocked"] == [
        {"key": "goal-1/batch-1", "open_backlog": 1}
    ]
    cover = seen["cover"]
    assert cover["subtask"]["key"] == "goal-1/batch-1/subtask-3"
    assert cover["subtask"]["origin"] == captured["key"]
    assert cover["backlog"]["state"] == "done"
    assert seen["done_cover"]["completed"] == ["goal-1/batch-1"]
    assert seen["push_preview"]["phase"] == "preview"
    push = seen["push"]
    assert push["item"]["key"] == "backlog-1" and push["item"]["parent"] is None
    assert seen["done_docs"]["completed"] == ["goal-1/batch-2", "goal-1"]
    assert seen["decision"]["decision"]["key"] == "goal-1/batch-1/decision-1"
    assert seen["decision2"]["decision"]["supersedes"] == "goal-1/batch-1/decision-1"
    assert seen["decision_update"]["decision"]["status"] == "deferred"
    assert seen["decision_get"]["decision"]["status"] == "superseded"
    assert len(seen["decisions"]["decisions"]) == 2
    assert seen["reopen"]["reopened"] == ["goal-1/batch-2", "goal-1"]
    assert seen["reopen"]["completed"] == [] and seen["reopen"]["blocked"] == []
    keys = [n["item"]["key"] for n in seen["tree"]["nodes"]]
    assert keys[0] == "goal-1" and keys[-1] == "backlog-1"
    assert "goal-1/batch-1/backlog-1" in keys
    item = seen["item"]
    assert item["item"]["state"] == "done"
    assert [d["key"] for d in item["decisions"]] == ["goal-1/batch-1/decision-1"]
    assert seen["pushed_old_key"]["item"]["key"] == "backlog-1"
    brief = seen["brief"]
    assert brief["backlog_counts"] == {"project": 1, "goal": 0, "batch": 0}
    (goal,) = brief["open_goals"]
    assert (goal["key"], goal["batches_done"], goal["batches_total"]) == (
        "goal-1",
        1,
        2,
    )
    assert brief["workflow"]["backlog"]["states"][0]["name"] == "open"
    rows = store.conn.execute(
        "SELECT DISTINCT actor_kind FROM event WHERE project_id = ? "
        "AND entity_type = 'item'",
        (project.id,),
    ).fetchall()
    assert {row[0] for row in rows} == {"claude", "system"}


def test_two_phase_tools_bind_their_tokens(project: Project, harness: Any) -> None:
    """A token applies only the exact call it was issued for."""
    del project

    async def scenario(client: ClientSession) -> list[str]:
        items = [{"kind": "goal", "title": "g"}]
        preview = await harness.ok(client, "items_create_bulk", **P, items=items)
        other = [{"kind": "goal", "title": "other"}]
        return [
            await harness.error(
                client, "items_create_bulk", **P, items=other,
                confirm_token=preview["confirm_token"],
            ),
            await harness.error(
                client, "backlog_push", **P, key="goal-1/backlog-1",
                confirm_token=preview["confirm_token"],
            ),
        ]  # fmt: skip

    first, second = harness.run(scenario)
    assert "does not match these arguments" in first
    assert "not found" in second or "another tool" in second
