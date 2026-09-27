"""decision_record can supersede an older decision of the same project."""

from collections.abc import Callable
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.services.decision_service import create_decision
from xoot.store.store import Store


@pytest.fixture(name="decisions")
def fixture_decisions(
    store: Store,
    ctx: WriteContext,
    project: Project,
    other_project: Project,
    make_session: Callable[..., Session],
) -> dict[str, Any]:
    """One decision in each project and an open session in the first."""
    return {
        "old": create_decision(store, project.id, DecisionCreate(title="old"), ctx),
        "foreign": create_decision(
            store, other_project.id, DecisionCreate(title="foreign"), ctx
        ),
        "session": f"xoot-S{make_session(project).number}",
    }


def test_supersede_through_decision_record(
    decisions: dict[str, Any],
    row_counts: Callable[[], dict[str, int]],
    harness: Any,
) -> None:
    """New and old change together; a second supersede or a foreign key is refused."""
    old, foreign = decisions["old"], decisions["foreign"]
    record = {"session": decisions["session"], "title": "t", "body": "b"}

    async def scenario(client: ClientSession) -> dict[str, Any]:
        new = await harness.ok(client, "decision_record", **record, supersedes=old.key)
        listed = await harness.ok(client, "decisions_list", project="xo")
        before = row_counts()
        again = await harness.error(
            client, "decision_record", **record, supersedes=old.key
        )
        cross = await harness.error(
            client, "decision_record", **record, supersedes=foreign.key
        )
        return {
            "new": new,
            "listed": listed,
            "again": again,
            "cross": cross,
            "unchanged": row_counts() == before,
        }

    out = harness.run(scenario)
    assert out["new"]["supersedes"] == old.key
    assert out["new"]["status"] == "locked"
    statuses = {d["key"]: d["status"] for d in out["listed"]["decisions"]}
    assert statuses == {old.key: "superseded", out["new"]["key"]: "locked"}
    assert "DecisionError:" in out["again"]
    assert "CrossProjectError:" in out["cross"]
    assert out["unchanged"]
