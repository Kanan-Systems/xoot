"""S5: two-phase calls for bulk create, subtree drop, reparent and session close."""

from collections.abc import Callable
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.store.store import Store

type Args = dict[str, Any]
type Flow = tuple[str, Args, Args, Args]

EXPIRED = "2000-01-01T00:00:00.000000Z"


@pytest.fixture(name="flow", params=["bulk", "drop", "reparent", "close"])
def fixture_flow(
    request: pytest.FixtureRequest,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> Flow:
    """One two-phase call: tool, arguments, changed arguments, another session's."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    other_goal = make_item(project, ItemKind.GOAL)
    keys = [f"xoot-S{make_session(project, batch.id).number}"]
    keys.append(f"xoot-S{make_session(project).number}")
    if request.param == "bulk":
        tool = "items_create_bulk"
        args: Args = {"items": [{"kind": "goal", "title": "g"}]}
        changed = {"items": [{"kind": "goal", "title": "other"}]}
    elif request.param == "close":
        tool = "session_close"
        args = {"dispositions": {batch.key: "carry_over"}}
        changed = {"dispositions": {batch.key: "dropped"}}
    else:
        tool = "item_update"
        moving = request.param == "reparent"
        args = {
            "key": batch.key if moving else goal.key,
            "expected_version": 1,
            "changes": {"parent": other_goal.key} if moving else {"state": "dropped"},
        }
        changed = {"expected_version": 2}
    return (
        tool,
        {"session": keys[0], **args},
        {"session": keys[0], **args, **changed},
        {"session": keys[1], **args},
    )


@pytest.fixture(name="expire_tokens")
def fixture_expire_tokens(store: Store) -> Callable[[], None]:
    """Factory: move every unused token's expiry into the past."""

    def expire() -> None:
        with store.write() as conn:
            conn.execute(
                "UPDATE confirm_token SET expires_at = ? WHERE used_at IS NULL",
                (EXPIRED,),
            )

    return expire


def test_two_phase(
    flow: Flow,
    row_counts: Callable[[], dict[str, int]],
    expire_tokens: Callable[[], None],
    harness: Any,
) -> None:
    """Preview writes only the token; the token is bound, expiring and single-use."""
    tool, args, changed, other = flow

    async def scenario(client: ClientSession) -> dict[str, Any]:
        before = row_counts()
        preview = await harness.ok(client, tool, **args)
        after = row_counts()
        token = preview["confirm_token"]
        errors = {
            "changed": await harness.error(
                client, tool, **changed, confirm_token=token
            ),
            "other": await harness.error(client, tool, **other, confirm_token=token),
        }
        expire_tokens()
        errors["expired"] = await harness.error(
            client, tool, **args, confirm_token=token
        )
        fresh = (await harness.ok(client, tool, **args))["confirm_token"]
        applied = await harness.ok(client, tool, **args, confirm_token=fresh)
        errors["replay"] = await harness.error(
            client, tool, **args, confirm_token=fresh
        )
        # sqlite_sequence is AUTOINCREMENT bookkeeping for the token row itself;
        # a write to any other table would show in that table's own count.
        written = {t: n - before[t] for t, n in after.items() if n != before[t]}
        written.pop("sqlite_sequence", None)
        return {"written": written, "preview": preview, "applied": applied, **errors}

    out = harness.run(scenario)
    assert out["written"] == {"confirm_token": 1}
    assert out["preview"]["phase"] == "preview" and out["preview"]["confirm_token"]
    assert out["applied"]["phase"] == "applied"
    assert "does not match these arguments" in out["changed"]
    assert "another session" in out["other"]
    assert "has expired" in out["expired"]
    assert "already been used" in out["replay"]
    for reason in ("changed", "other", "expired", "replay"):
        assert out["preview"]["confirm_token"] not in out[reason]
