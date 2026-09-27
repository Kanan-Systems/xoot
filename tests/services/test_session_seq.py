"""
Session order comes from the project's sequence counter, not the clock.

The write clock is monkeypatched to step backwards; closing must still retire
the right stale backlogs and still succeed.
"""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, tzinfo

import pytest

from xoot.models.event.actor import Actor
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.services import write_scope
from xoot.services.item_service import capture, get_item
from xoot.services.session_close_service import close_session, preview_close
from xoot.services.session_service import start_session
from xoot.store.store import Store

type SetClock = Callable[[int, int], None]


@pytest.fixture(name="set_clock")
def fixture_set_clock(monkeypatch: pytest.MonkeyPatch) -> SetClock:
    """Factory: pin the time every later write scope reads, as (hour, minute)."""
    current = [datetime(2026, 9, 27, 12, 0, tzinfo=UTC)]

    class PinnedDatetime(datetime):
        """datetime whose now() returns the pinned time."""

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return current[0].astimezone(tz)

    monkeypatch.setattr(write_scope, "datetime", PinnedDatetime)

    def set_clock(hour: int, minute: int) -> None:
        current[0] = datetime(2026, 9, 27, hour, minute, tzinfo=UTC)

    return set_clock


def _park(store: Store, session: Session, item: Item, user: Actor) -> Session:
    """Close a session, leaving one item in its session backlog."""
    request = SessionClose(dispositions={item.id: Disposition.SESSION_BACKLOG})
    return close_session(store, session.id, request, user)


def _start(store: Store, project: Project, user: Actor) -> Session:
    return start_session(store, project.id, SessionStart(title="s"), user).session


def test_clock_step_back_between_sessions(
    store: Store, project: Project, user: Actor, set_clock: SetClock
) -> None:
    """(a) S2 starts at an earlier wall time than S1 closed; S2's close retires S1's backlog."""
    set_clock(12, 0)
    first = _start(store, project, user)
    parked = capture(store, first.id, ItemDraft(title="parked"), user)
    set_clock(12, 10)
    first = _park(store, first, parked, user)
    set_clock(11, 0)
    second = start_session(store, project.id, SessionStart(title="s2"), user)
    assert second.session.started_at < first.closed_at
    assert first.close_seq < second.session.start_seq
    assert [item.id for item in second.pending] == [parked.id]
    set_clock(11, 10)
    plan = preview_close(store, second.session.id, SessionClose())
    assert [change.item_id for change in plan.auto_backlog] == [parked.id]
    close_session(store, second.session.id, SessionClose(), user)
    moved = get_item(store, parked.id)
    assert (moved.state, moved.backlog_session_id) == ("backlogged", None)


def test_clock_step_back_during_a_session(
    store: Store, project: Project, user: Actor, set_clock: SetClock
) -> None:
    """(b) A session closed "before" it started still closes, and its backlog is still retired."""
    set_clock(12, 0)
    first = _start(store, project, user)
    parked = capture(store, first.id, ItemDraft(title="parked"), user)
    set_clock(11, 0)
    first = _park(store, first, parked, user)
    assert first.closed_at < first.started_at
    assert first.close_seq > first.start_seq
    set_clock(11, 5)
    second = _start(store, project, user)
    set_clock(11, 10)
    close_session(store, second.id, SessionClose(), user)
    moved = get_item(store, parked.id)
    assert (moved.state, moved.backlog_session_id) == ("backlogged", None)


def test_later_close_with_earlier_timestamp_is_kept(
    store: Store, project: Project, user: Actor, set_clock: SetClock
) -> None:
    """A backlog parked after S started stays, even if its clock reads earlier."""
    set_clock(12, 0)
    other = _start(store, project, user)
    parked = capture(store, other.id, ItemDraft(title="parked"), user)
    current = _start(store, project, user)
    set_clock(10, 0)
    other = _park(store, other, parked, user)
    assert other.closed_at < current.started_at
    close_session(store, current.id, SessionClose(), user)
    assert get_item(store, parked.id).backlog_session_id == other.id


def test_sequence_values_come_from_one_project_counter(
    store: Store,
    project: Project,
    other_project: Project,
    user: Actor,
    make_session: Callable[..., Session],
) -> None:
    """Starts and closes share the counter; each project has its own."""
    first = make_session(project)
    second = make_session(project)
    closed = close_session(store, first.id, SessionClose(), user)
    elsewhere = make_session(other_project)
    assert (first.start_seq, second.start_seq, closed.close_seq) == (1, 2, 3)
    assert elsewhere.start_seq == 1


@pytest.mark.parametrize(
    "assignment",
    [
        "status = 'closed', closed_at = started_at, close_seq = NULL",
        "close_seq = start_seq + 1",
        "status = 'closed', closed_at = started_at, close_seq = start_seq",
    ],
)
def test_schema_enforces_close_seq(
    store: Store, project: Project, user: Actor, assignment: str
) -> None:
    """close_seq is NULL exactly while open, and always after start_seq."""
    _start(store, project, user)
    raw = sqlite3.connect(store.path, autocommit=True)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            raw.execute(f"UPDATE session SET {assignment}")
    finally:
        raw.close()
