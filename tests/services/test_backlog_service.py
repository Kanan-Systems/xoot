"""Backlog scopes and open-session backlogs, read from one snapshot."""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.exceptions.invalid_id_error import InvalidIdError
from xoot.models.event.actor import Actor
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.services.backlog_service import (
    backlog_items,
    open_session_backlog,
    session_backlogs,
)
from xoot.services.item_service import capture
from xoot.services.session_close_service import close_session
from xoot.store.store import Store


@pytest.fixture(name="backlogs")
def fixture_backlogs(
    store: Store,
    user: Actor,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> dict[str, Any]:
    """
    A project backlog item, a capture in an open session, one in a closed
    session, an open unfiled subtask and a done unfiled subtask.
    """
    open_session = make_session(project)
    closed = make_session(project)
    held = capture(store, open_session.id, ItemDraft(title="held"), user)
    parked = capture(store, closed.id, ItemDraft(title="parked"), user)
    keep = SessionClose(dispositions={parked.id: Disposition.SESSION_BACKLOG})
    close_session(store, closed.id, keep, user)
    return {
        "project": make_item(project, ItemKind.SUBTASK, state="backlogged"),
        "held": held,
        "parked": parked,
        "loose": make_item(project, ItemKind.SUBTASK),
        "done": make_item(project, ItemKind.SUBTASK, state="done"),
        "open_session": open_session,
        "closed": closed,
    }


def _keys(items: list[Item]) -> list[str]:
    return [item.key for item in items]


def test_each_scope_lists_its_items(
    store: Store, project: Project, backlogs: dict[str, Any]
) -> None:
    """session, project and unfiled pick the same items backlog_list does."""
    held, parked = backlogs["held"], backlogs["parked"]
    with store.read() as conn:
        assert _keys(backlog_items(conn, project.id, "session")) == [
            held.key,
            parked.key,
        ]
        assert _keys(backlog_items(conn, project.id, "project")) == [
            backlogs["project"].key
        ]
        unfiled = _keys(backlog_items(conn, project.id, "unfiled"))
    assert backlogs["loose"].key in unfiled
    assert backlogs["done"].key not in unfiled
    assert held.key in unfiled


def test_open_session_backlog_skips_closed_sessions(
    store: Store, project: Project, backlogs: dict[str, Any]
) -> None:
    """Only the capture of the still-open session is held."""
    with store.read() as conn:
        held = open_session_backlog(conn, project.id)
    assert _keys(held) == [backlogs["held"].key]


def test_session_backlogs_group_per_open_session(
    store: Store,
    project: Project,
    make_session: Callable[..., Session],
    backlogs: dict[str, Any],
) -> None:
    """Every open session appears, in order, with an empty backlog if need be."""
    empty = make_session(project)
    with store.read() as conn:
        grouped = session_backlogs(conn, project.id)
    assert [entry.session.id for entry in grouped] == [
        backlogs["open_session"].id,
        empty.id,
    ]
    assert _keys(list(grouped[0].items)) == [backlogs["held"].key]
    assert not grouped[1].items


def test_other_projects_are_not_read(
    store: Store,
    other_project: Project,
    backlogs: dict[str, Any],
) -> None:
    """A project with no backlog of its own sees none of the first's items."""
    assert backlogs
    with store.read() as conn:
        assert not backlog_items(conn, other_project.id, "session")
        assert not open_session_backlog(conn, other_project.id)
        assert not session_backlogs(conn, other_project.id)


@pytest.mark.parametrize("bad", ["1", True, 0])
def test_a_raw_id_must_be_an_int(store: Store, bad: object) -> None:
    """Ids are checked before any SQL runs."""
    with store.read() as conn:
        with pytest.raises(InvalidIdError):
            backlog_items(conn, bad, "session")
        with pytest.raises(InvalidIdError):
            session_backlogs(conn, bad)
