"""brief_get caps its open sessions and flags the cut."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.server.brief import LIST_MAX


def test_brief_get_caps_open_sessions(
    project: Project, make_session: Callable[..., Session], harness: Any
) -> None:
    """One session past the cap: the first LIST_MAX are listed, truncated is set."""
    for _ in range(LIST_MAX + 1):
        make_session(project)

    async def scenario(client: ClientSession) -> Any:
        return await harness.ok(client, "brief_get", project="xo")

    brief = harness.run(scenario)
    assert [s["key"] for s in brief["open_sessions"]] == [
        f"xoot-S{n}" for n in range(1, LIST_MAX + 1)
    ]
    assert brief["open_sessions_truncated"] is True
