"""Every write's client comes from client_info, per call; the actor is Claude."""

from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.project.project import Project
from xoot.store.store import Store


@pytest.mark.parametrize(
    ("client_name", "expected"),
    [
        ("claude-code", "code"),
        ("Claude-Code-CLI", "code"),
        ("claude-ai", "chat"),
        ("some other client", "chat"),
    ],
)
def test_write_client_follows_client_info(
    store: Store,
    project: Project,
    harness: Any,
    client_name: str,
    expected: str,
) -> None:
    """claude-code in any case means code, anything else chat."""

    async def scenario(client: ClientSession) -> None:
        await harness.ok(client, "item_create", project="xo", kind="goal", title="g")

    harness.run(scenario, client_name=client_name)
    events = store.conn.execute(
        "SELECT DISTINCT actor_kind, client FROM event "
        "WHERE project_id = ? AND entity_type = 'item'",
        (project.id,),
    ).fetchall()
    assert [tuple(row) for row in events] == [("claude", expected)]


def test_two_clients_work_on_one_goal(
    store: Store, project: Project, harness: Any
) -> None:
    """A chat and Claude Code both write to the same goal; each is labelled."""

    async def create(client: ClientSession) -> None:
        await harness.ok(client, "item_create", project="xo", kind="goal", title="g")

    async def add(client: ClientSession) -> None:
        await harness.ok(
            client,
            "item_create",
            project="xo",
            kind="batch",
            title="b",
            parent="goal-1",
        )

    harness.run(create, client_name="claude-ai")
    harness.run(add, client_name="claude-code")
    rows = store.conn.execute(
        "SELECT client FROM event WHERE project_id = ? AND entity_type = 'item' "
        "ORDER BY id",
        (project.id,),
    ).fetchall()
    assert [row[0] for row in rows] == ["chat", "code"]
