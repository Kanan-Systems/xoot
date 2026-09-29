"""History and decision reads used by the views."""

from collections.abc import Callable

import pytest

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.services.decision_reads import decision_detail, owned_decisions
from xoot.services.decision_service import create_decision
from xoot.services.history_service import latest_event_id, recent_events
from xoot.services.item_service import update_item
from xoot.store.store import Store


def test_recent_events_are_newest_first_and_capped(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """Three updates after the create: the newest two come back, newest first."""
    item = make_item(project, ItemKind.GOAL)
    for version, title in enumerate(("a", "b", "c"), start=1):
        update_item(store, item.id, version, ItemUpdate(title=title), ctx)
    with store.read() as conn:
        events = recent_events(conn, item.id, 2)
    assert [event.after["title"] for event in events if event.after] == ["c", "b"]


def test_latest_event_id_moves_on_every_write(
    store: Store,
    ctx: WriteContext,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
) -> None:
    """The marker grows with a write, and ignores other projects' writes."""
    with store.read() as conn:
        before = latest_event_id(conn, project.id)
    item = make_item(project, ItemKind.GOAL)
    with store.read() as conn:
        after_create = latest_event_id(conn, project.id)
    make_item(other_project, ItemKind.GOAL)
    with store.read() as conn:
        assert latest_event_id(conn, project.id) == after_create
    update_item(store, item.id, 1, ItemUpdate(title="x"), ctx)
    with store.read() as conn:
        assert before < after_create < latest_event_id(conn, project.id)


def test_latest_event_id_is_zero_without_events(store: Store) -> None:
    """A project id with no events reports 0."""
    with store.read() as conn:
        assert latest_event_id(conn, 999) == 0


def test_decision_reads(
    store: Store, ctx: WriteContext, project: Project, make_item: Callable[..., Item]
) -> None:
    """The detail carries the body; owned lists only that item's, newest first."""
    goal = make_item(project, ItemKind.GOAL)
    other = make_item(project, ItemKind.GOAL)
    older = create_decision(
        store,
        project.id,
        DecisionCreate(owner_item_id=goal.id, title="a", body="body a"),
        ctx,
    )
    newer = create_decision(
        store, project.id, DecisionCreate(owner_item_id=goal.id, title="b"), ctx
    )
    create_decision(
        store, project.id, DecisionCreate(owner_item_id=other.id, title="c"), ctx
    )
    with store.read() as conn:
        assert decision_detail(conn, project.id, older.key).body == "body a"
        assert [d.key for d in owned_decisions(conn, goal, 10)] == [
            newer.key,
            older.key,
        ]
        assert [d.key for d in owned_decisions(conn, goal, 1)] == [newer.key]


@pytest.mark.parametrize("key", ["goal-1/decision-99", "not a key"])
def test_decision_detail_refuses_unknown_keys(
    store: Store, project: Project, key: str
) -> None:
    """A missing or malformed key is NotFoundError."""
    with store.read() as conn:
        with pytest.raises(NotFoundError):
            decision_detail(conn, project.id, key)
