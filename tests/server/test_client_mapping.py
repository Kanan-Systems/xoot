"""S7: the session's client comes from client_info; every write reuses it."""

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
def test_session_client_follows_client_info(
    store: Store,
    project: Project,
    harness: Any,
    client_name: str,
    expected: str,
) -> None:
    """claude-code in any case means code, anything else chat; writes are Claude's."""
    assert project.key_prefix == "xoot"

    async def scenario(client: ClientSession) -> dict[str, Any]:
        started = await harness.ok(client, "session_start", project="xo", title="t")
        key = started["session"]["key"]
        await harness.ok(client, "capture", session=key, title="side")
        return started

    started = harness.run(scenario, client_name=client_name)
    assert started["session"]["client"] == expected
    assert started["client_info"] == {"name": client_name, "version": "9.9.9"}
    events = store.conn.execute(
        "SELECT DISTINCT actor_kind, client FROM event WHERE session_id IS NOT NULL"
    ).fetchall()
    assert [tuple(row) for row in events] == [("claude", expected)]
