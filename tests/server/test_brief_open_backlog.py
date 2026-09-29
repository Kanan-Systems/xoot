"""brief_get lists items held by open sessions (kanan-28), capped and flagged."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.models.event.actor import Actor
from xoot.models.item.item_draft import ItemDraft
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.server.brief import LIST_MAX
from xoot.services.item_service import capture
from xoot.store.store import Store


def _brief(harness: Any) -> Any:
    async def scenario(client: ClientSession) -> Any:
        return await harness.ok(client, "brief_get", project="xo")

    return harness.run(scenario)


def test_brief_get_shows_open_session_backlog(
    store: Store,
    user: Actor,
    project: Project,
    make_session: Callable[..., Session],
    harness: Any,
) -> None:
    """A capture in an open session is listed; pending stays closed-only."""
    session = make_session(project)
    held = capture(store, session.id, ItemDraft(title="held"), user)
    brief = _brief(harness)
    assert [i["key"] for i in brief["open_session_backlog"]] == [held.key]
    assert brief["open_session_backlog"][0]["backlog_session"] == "xoot-S1"
    assert brief["open_session_backlog_truncated"] is False
    assert not brief["pending_session_backlog"]


def test_brief_get_caps_open_session_backlog(
    store: Store,
    user: Actor,
    project: Project,
    make_session: Callable[..., Session],
    harness: Any,
) -> None:
    """One item past the cap: LIST_MAX are listed and truncated is set."""
    session = make_session(project)
    for n in range(LIST_MAX + 1):
        capture(store, session.id, ItemDraft(title=f"held {n}"), user)
    brief = _brief(harness)
    assert len(brief["open_session_backlog"]) == LIST_MAX
    assert brief["open_session_backlog_truncated"] is True
