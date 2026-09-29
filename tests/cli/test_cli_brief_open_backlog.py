"""`xoot brief` shows the items open sessions hold (kanan-28)."""

from collections.abc import Callable
from typing import Any

from xoot.models.event.actor import Actor
from xoot.models.item.item_draft import ItemDraft
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.server.brief import LIST_MAX
from xoot.services.item_service import capture
from xoot.store.store import Store


def test_brief_text_lists_open_session_backlog(
    store: Store,
    user: Actor,
    project: Project,
    make_session: Callable[..., Session],
    xoot: Any,
) -> None:
    """The text brief has an "Open session backlog" section with the capture."""
    session = make_session(project)
    capture(store, session.id, ItemDraft(title="held item"), user)
    out = xoot("brief", "--project", "xo").out
    section = out.split("Open session backlog\n", 1)[1].split("\n\n", 1)[0]
    assert "xoot-1" in section
    assert "held item" in section


def test_brief_text_says_none_without_held_items(project: Project, xoot: Any) -> None:
    """With nothing held the section reads (none)."""
    assert project.id
    out = xoot("brief", "--project", "xo").out
    assert "Open session backlog\n  (none)" in out


def test_brief_json_carries_the_field_and_the_cut(
    store: Store,
    user: Actor,
    project: Project,
    make_session: Callable[..., Session],
    xoot: Any,
) -> None:
    """--json has the capped list and the truncated flag; text notes the cut."""
    session = make_session(project)
    for n in range(LIST_MAX + 1):
        capture(store, session.id, ItemDraft(title=f"held {n}"), user)
    brief = xoot("brief", "--project", "xo", "--json").json()
    assert len(brief["open_session_backlog"]) == LIST_MAX
    assert brief["open_session_backlog_truncated"] is True
    text = xoot("brief", "--project", "xo").out
    assert f"(first {LIST_MAX} shown; more are held)" in text
