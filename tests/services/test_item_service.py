"""Item creation, capture and update rules, including T3 concurrency."""

import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.exceptions.state_error import StateError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.repositories.session import session_item_ref_db
from xoot.services.item_service import capture, create_item, get_item, update_item
from xoot.services.project_service import get_project
from xoot.services.session_close_service import close_session
from xoot.store.store import Store

WORKERS = 8
ITEMS_PER_WORKER = 25


def _create_items(db_path: str, project_id: int, barrier: Any, results: Any) -> None:
    """Spawned worker: create items as fast as possible, counting busy errors."""
    ctx = WriteContext(actor=Actor(kind=ActorKind.CLAUDE, client=Client.CODE))
    numbers, busy = [], 0
    with Store.open(Path(db_path)) as store:
        barrier.wait(timeout=60)
        started = time.perf_counter()
        for index in range(ITEMS_PER_WORKER):
            request = ItemCreate(kind=ItemKind.SUBTASK, title=f"{os.getpid()}-{index}")
            try:
                numbers.append(create_item(store, project_id, request, ctx).number)
            except sqlite3.OperationalError as exc:
                if exc.sqlite_errorcode & 0xFF != sqlite3.SQLITE_BUSY:
                    raise
                busy += 1
        results.put((numbers, busy, time.perf_counter() - started, os.getpid()))


def test_concurrent_creates_get_unique_contiguous_numbers(
    store: Store,
    project: Project,
    event_kinds: Callable[[Project], list[tuple[str, str]]],
    spawn_workers: Any,
) -> None:
    """T3: 8 processes x 25 items -> numbers 1..200, 200 events, no busy errors."""
    events_before = len(event_kinds(project))
    results = spawn_workers(_create_items, [(str(store.path), project.id)] * WORKERS)
    numbers = sorted(n for worker_numbers, *_ in results for n in worker_numbers)
    assert sum(busy for _, busy, *_ in results) == 0
    pids = {pid for *_, pid in results}
    assert len(pids) == WORKERS and os.getpid() not in pids
    assert numbers == list(range(1, WORKERS * ITEMS_PER_WORKER + 1))
    new_events = event_kinds(project)[events_before:]
    assert new_events == [("item", "create")] * (WORKERS * ITEMS_PER_WORKER)
    assert (
        get_project(store, project.id).next_item_number
        == WORKERS * ITEMS_PER_WORKER + 1
    )


def test_keys_come_from_the_project_counter(
    project: Project, other_project: Project, make_item: Callable[..., Item]
) -> None:
    """Keys are <prefix>-<n>, numbered per project."""
    assert make_item(project, ItemKind.GOAL).key == "xoot-1"
    assert make_item(project, ItemKind.SUBTASK).key == "xoot-2"
    assert make_item(other_project, ItemKind.GOAL).key == "nova-1"


def test_state_defaults_to_open_and_is_validated(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """New items start open; a named state must exist in the workflow."""
    assert make_item(project, ItemKind.GOAL).state == "open"
    assert make_item(project, ItemKind.GOAL, state="blocked").state == "blocked"
    with pytest.raises(StateError, match="not in the active workflow"):
        make_item(project, ItemKind.GOAL, state="someday")


def test_session_backlog_only_in_backlogged_state(
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """backlog_session_id needs a backlogged state."""
    session = make_session(project)
    with pytest.raises(StateError, match="backlogged"):
        make_item(project, ItemKind.SUBTASK, backlog_session_id=session.id)
    item = make_item(
        project, ItemKind.SUBTASK, state="backlogged", backlog_session_id=session.id
    )
    assert item.backlog_session_id == session.id


def test_capture_makes_an_unfiled_session_backlog_subtask(
    store: Store, project: Project, make_session: Callable[..., Session], claude: Actor
) -> None:
    """T5: capture creates an unfiled subtask parked in the session's backlog."""
    session = make_session(project)
    item = capture(store, session.id, ItemDraft(title="idea", body="later"), claude)
    assert (item.kind, item.parent_id, item.unfiled) == (ItemKind.SUBTASK, None, True)
    assert item.state == "backlogged"
    assert item.backlog_session_id == session.id
    with store.read() as conn:
        refs = session_item_ref_db.list_for_session(conn, session.id)
    assert [ref.item_id for ref in refs] == [item.id]


def test_capture_needs_an_open_session(
    store: Store, project: Project, make_session: Callable[..., Session], user: Actor
) -> None:
    """Capturing into a closed session is refused."""
    session = make_session(project)
    close_session(store, session.id, SessionClose(), user)
    with pytest.raises(SessionStateError):
        capture(store, session.id, ItemDraft(title="late"), user)


def test_writes_in_a_session_link_the_item(
    store: Store,
    project: Project,
    other_project: Project,
    make_session: Callable[..., Session],
    user: Actor,
) -> None:
    """F5: the session must be open and in the project; the item is linked."""
    session = make_session(project)
    ctx = WriteContext(actor=user, session_id=session.id)
    item = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="g"), ctx
    )
    with store.read() as conn:
        assert session_item_ref_db.open_session_ids(conn, item.id) == [session.id]
    with pytest.raises(CrossProjectError):
        create_item(
            store, other_project.id, ItemCreate(kind=ItemKind.GOAL, title="g"), ctx
        )
    close_session(
        store, session.id, SessionClose(dispositions={item.id: "carry_over"}), user
    )
    with pytest.raises(SessionStateError):
        update_item(store, item.id, 1, ItemUpdate(title="x"), ctx)


def test_leaving_the_backlog_clears_the_session_backlog(
    store: Store,
    project: Project,
    make_session: Callable[..., Session],
    user: Actor,
    ctx: WriteContext,
) -> None:
    """F4: moving out of the backlogged category drops backlog_session_id."""
    item = capture(store, make_session(project).id, ItemDraft(title="idea"), user)
    moved = update_item(store, item.id, 1, ItemUpdate(state="active"), ctx)
    assert (moved.state, moved.backlog_session_id, moved.version) == ("active", None, 2)
    with pytest.raises(StateError):
        update_item(
            store,
            item.id,
            2,
            ItemUpdate(backlog_session_id=item.backlog_session_id),
            ctx,
        )


def test_unchanged_update_keeps_the_version(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """Setting fields to their current values writes nothing."""
    item = make_item(project, ItemKind.GOAL, title="same")
    assert update_item(store, item.id, 1, ItemUpdate(title="same"), ctx) == item


def test_missing_item(store: Store) -> None:
    """Unknown ids raise NotFoundError."""
    with pytest.raises(NotFoundError):
        get_item(store, 12345)
