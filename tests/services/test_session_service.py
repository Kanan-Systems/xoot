"""F10: session start links focus items, offers pending backlog, warns on overlap."""

from collections.abc import Callable

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.models.event.actor import Actor
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.session import session_item_ref_db
from xoot.services.item_service import capture
from xoot.services.session_close_service import close_session
from xoot.services.session_service import get_session, start_session
from xoot.store.store import Store


def test_start_numbers_and_links(
    store: Store, project: Project, make_item: Callable[..., Item], claude: Actor
) -> None:
    """Sessions are numbered per project, take the actor's client, link focus."""
    goal = make_item(project, ItemKind.GOAL)
    first = start_session(store, project.id, SessionStart(title="a"), claude).session
    second = start_session(
        store, project.id, SessionStart(title="b", focus_item_ids=(goal.id,)), claude
    ).session
    assert (first.number, second.number) == (1, 2)
    assert second.client is Client.CODE
    assert second.status is SessionStatus.OPEN and second.closed_at is None
    assert get_session(store, second.id) == second
    with store.read() as conn:
        assert session_item_ref_db.open_session_ids(conn, goal.id) == [second.id]


def test_pending_lists_backlogs_of_closed_sessions_only(
    store: Store, project: Project, user: Actor
) -> None:
    """Items parked by a closed session are offered; an open session's are not."""
    closed = start_session(store, project.id, SessionStart(title="a"), user).session
    parked = capture(store, closed.id, ItemDraft(title="parked"), user)
    close_session(
        store,
        closed.id,
        SessionClose(dispositions={parked.id: Disposition.SESSION_BACKLOG}),
        user,
    )
    still_open = start_session(store, project.id, SessionStart(title="b"), user).session
    capture(store, still_open.id, ItemDraft(title="in flight"), user)
    result = start_session(store, project.id, SessionStart(title="c"), user)
    assert [item.id for item in result.pending] == [parked.id]


def test_focus_shared_with_open_session_warns(
    store: Store, project: Project, make_item: Callable[..., Item], user: Actor
) -> None:
    """Overlap with another open session is allowed but reported."""
    goal = make_item(project, ItemKind.GOAL)
    focus = SessionStart(title="s", focus_item_ids=(goal.id,))
    first = start_session(store, project.id, focus, user)
    second = start_session(store, project.id, focus, user)
    assert first.warnings == ()
    assert [(w.item_id, w.key, w.open_session_ids) for w in second.warnings] == [
        (goal.id, "xoot-1", (first.session.id,))
    ]
    close_session(
        store,
        first.session.id,
        SessionClose(dispositions={goal.id: Disposition.CARRY_OVER}),
        user,
    )
    third = start_session(store, project.id, focus, user)
    assert [w.open_session_ids for w in third.warnings] == [(second.session.id,)]


def test_focus_from_another_project_is_rejected(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
    user: Actor,
) -> None:
    """Focus items must belong to the session's project."""
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        start_session(
            store,
            project.id,
            SessionStart(title="s", focus_item_ids=(foreign.id,)),
            user,
        )
