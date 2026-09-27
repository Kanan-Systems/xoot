"""T7: session close dispositions, stale backlog retirement, pure preview."""

from collections.abc import Callable

import pytest

from xoot.exceptions.disposition_error import DispositionError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.session import session_item_ref_db
from xoot.services.item_service import capture, get_item, update_item
from xoot.services.session_close_service import close_session, preview_close
from xoot.store.store import Store

ALL_FOUR = (
    Disposition.CARRY_OVER,
    Disposition.SESSION_BACKLOG,
    Disposition.PROJECT_BACKLOG,
    Disposition.DROPPED,
)


@pytest.fixture(name="linked")
def fixture_linked(
    project: Project,
    make_session: Callable[..., Session],
    make_item: Callable[..., Item],
) -> tuple[Session, list[Item], Item]:
    """An open session linked to four active subtasks and one done subtask."""
    active = [make_item(project, ItemKind.SUBTASK, state="active") for _ in ALL_FOUR]
    done = make_item(project, ItemKind.SUBTASK, state="done")
    session = make_session(project, *(item.id for item in active), done.id)
    return session, active, done


def test_missing_dispositions_are_rejected(
    store: Store,
    user: Actor,
    linked: tuple[Session, list[Item], Item],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Every open linked item needs a disposition; done ones do not."""
    session, active, _ = linked
    before = row_counts()
    request = SessionClose(dispositions={active[0].id: Disposition.CARRY_OVER})
    with pytest.raises(DispositionError) as caught:
        close_session(store, session.id, request, user)
    assert caught.value.item_ids == tuple(item.id for item in active[1:])
    assert row_counts() == before


@pytest.mark.parametrize("target", ["done", "unlinked"])
def test_unexpected_dispositions_are_rejected(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    linked: tuple[Session, list[Item], Item],
    target: str,
) -> None:
    """A disposition for a done or unlinked item is an error."""
    session, active, done = linked
    extra = done if target == "done" else make_item(project, ItemKind.GOAL)
    dispositions = {item.id: Disposition.CARRY_OVER for item in active}
    dispositions[extra.id] = Disposition.DROPPED
    with pytest.raises(DispositionError, match="need none"):
        preview_close(store, session.id, SessionClose(dispositions=dispositions))


def test_each_disposition_has_its_effect(
    store: Store, user: Actor, linked: tuple[Session, list[Item], Item]
) -> None:
    """carry_over keeps state; the backlogs and dropped use default states."""
    session, active, done = linked
    dispositions = dict(zip((item.id for item in active), ALL_FOUR, strict=True))
    closed = close_session(
        store, session.id, SessionClose(summary="wrap", dispositions=dispositions), user
    )
    after = [get_item(store, item.id) for item in active]
    assert [(i.state, i.backlog_session_id) for i in after] == [
        ("active", None),
        ("backlogged", session.id),
        ("backlogged", None),
        ("dropped", None),
    ]
    assert [i.version for i in after] == [1, 2, 2, 2]
    assert get_item(store, done.id) == done
    assert closed.status is SessionStatus.CLOSED
    assert (closed.summary, closed.closed_at is not None) == ("wrap", True)
    with store.read() as conn:
        refs = {
            r.item_id: r.disposition
            for r in session_item_ref_db.list_for_session(conn, session.id)
        }
    assert refs == {**dispositions, done.id: None}


def test_preview_writes_nothing(
    store: Store,
    linked: tuple[Session, list[Item], Item],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """The preview reports the plan (missing ones included) and changes no row."""
    session, active, _ = linked
    request = SessionClose(dispositions={active[3].id: Disposition.DROPPED})
    before, changes = row_counts(), store.conn.total_changes
    plan = preview_close(store, session.id, request)
    assert (row_counts(), store.conn.total_changes) == (before, changes)
    assert plan.required_item_ids == tuple(item.id for item in active)
    assert plan.missing_item_ids == tuple(item.id for item in active[:3])
    assert [(c.item_id, c.after) for c in plan.changes] == [
        (active[3].id, {"state": "dropped"})
    ]
    assert get_item(store, active[3].id).state == "active"


def test_stale_session_backlogs_move_to_project_backlog(
    store: Store,
    project: Project,
    user: Actor,
    make_session: Callable[..., Session],
    event_kinds: Callable[[Project], list[tuple[str, str]]],
) -> None:
    """
    F9: closing S retires backlogs of sessions that closed before S started,
    including items S carried over; an item S re-parks in its own backlog,
    and backlogs of sessions that closed after S started, are kept.
    """
    late = make_session(project)
    early = make_session(project)
    stale = capture(store, early.id, ItemDraft(title="stale"), user)
    kept_by_s = capture(store, early.id, ItemDraft(title="rehomed"), user)
    carried = capture(store, early.id, ItemDraft(title="carried"), user)
    close_session(
        store,
        early.id,
        SessionClose(
            dispositions={
                stale.id: Disposition.SESSION_BACKLOG,
                kept_by_s.id: Disposition.SESSION_BACKLOG,
                carried.id: Disposition.SESSION_BACKLOG,
            }
        ),
        user,
    )
    current = make_session(project, carried.id)
    fresh = capture(store, late.id, ItemDraft(title="fresh"), user)
    close_session(
        store,
        late.id,
        SessionClose(dispositions={fresh.id: Disposition.SESSION_BACKLOG}),
        user,
    )
    # Parking at close changed nothing (already in early's backlog): still v1.
    update_item(
        store,
        kept_by_s.id,
        1,
        ItemUpdate(body="touched in S"),
        WriteContext(actor=user, session_id=current.id),
    )
    request = SessionClose(
        dispositions={
            kept_by_s.id: Disposition.SESSION_BACKLOG,
            carried.id: Disposition.CARRY_OVER,
        }
    )
    plan = preview_close(store, current.id, request)
    assert [change.item_id for change in plan.auto_backlog] == [stale.id, carried.id]
    seen = len(event_kinds(project))
    close_session(store, current.id, request, user)
    assert get_item(store, stale.id).backlog_session_id is None
    assert get_item(store, stale.id).state == "backlogged"
    assert get_item(store, carried.id).backlog_session_id is None
    assert get_item(store, kept_by_s.id).backlog_session_id == current.id
    assert get_item(store, fresh.id).backlog_session_id == late.id
    assert event_kinds(project)[seen:] == [
        ("session", "dispose"),
        ("session", "dispose"),
        ("item", "update"),
        ("item", "update"),
        ("item", "update"),
        ("session", "close"),
    ]


def test_closed_session_cannot_close_again(
    store: Store, project: Project, user: Actor, make_session: Callable[..., Session]
) -> None:
    """Closing (or previewing) a closed session is refused."""
    session = make_session(project)
    close_session(store, session.id, SessionClose(), user)
    with pytest.raises(SessionStateError):
        close_session(store, session.id, SessionClose(), user)
    with pytest.raises(SessionStateError):
        preview_close(store, session.id, SessionClose())


@pytest.fixture(name="family")
def fixture_family(
    project: Project,
    make_session: Callable[..., Session],
    make_item: Callable[..., Item],
) -> tuple[Session, Item, Item]:
    """An open session linked to an active batch and its active subtask."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id, state="active")
    child = make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="active")
    return make_session(project, batch.id, child.id), batch, child


@pytest.mark.parametrize(
    "case",
    [
        (Disposition.DROPPED, Disposition.CARRY_OVER, True),
        (Disposition.PROJECT_BACKLOG, Disposition.CARRY_OVER, True),
        (Disposition.SESSION_BACKLOG, Disposition.CARRY_OVER, True),
        (Disposition.DROPPED, Disposition.PROJECT_BACKLOG, True),
        (Disposition.PROJECT_BACKLOG, Disposition.SESSION_BACKLOG, False),
        (Disposition.DROPPED, Disposition.DROPPED, False),
        (Disposition.CARRY_OVER, Disposition.CARRY_OVER, False),
    ],
)
def test_close_warns_about_live_children_of_parked_parents(
    store: Store,
    user: Actor,
    family: tuple[Session, Item, Item],
    case: tuple[Disposition, Disposition, bool],
) -> None:
    """Decision 6: states stay independent; the preview only warns, and close still works."""
    session, batch, child = family
    parent_to, child_to, warned = case
    request = SessionClose(dispositions={batch.id: parent_to, child.id: child_to})
    plan = preview_close(store, session.id, request)
    expected = [(child.key, batch.key)] if warned else []
    assert [(w.key, w.parent_key) for w in plan.warnings] == expected
    assert (
        close_session(store, session.id, request, user).status is SessionStatus.CLOSED
    )


def test_close_warns_about_a_parent_parked_earlier(
    store: Store,
    ctx: WriteContext,
    project: Project,
    make_session: Callable[..., Session],
    make_item: Callable[..., Item],
) -> None:
    """A parent already backlogged outside this session counts too."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    update_item(store, batch.id, 1, ItemUpdate(state="backlogged"), ctx)
    child = make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="active")
    session = make_session(project, child.id)
    request = SessionClose(dispositions={child.id: Disposition.CARRY_OVER})
    warnings = preview_close(store, session.id, request).warnings
    assert [(w.key, w.parent_key, w.parent_category) for w in warnings] == [
        (child.key, batch.key, "backlogged")
    ]
