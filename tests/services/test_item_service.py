"""Item creation and update rules, including concurrent creation."""

import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.state_error import StateError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.services.item_service import create_item, get_item, update_item
from xoot.services.lookups import require_item
from xoot.store.store import Store

WORKERS = 8
ITEMS_PER_WORKER = 25


def _create_items(
    db_path: str, project_id: int, batch_id: int, barrier: Any, results: Any
) -> None:
    """Spawned worker: create subtasks as fast as possible, counting busy errors."""
    ctx = WriteContext(actor=Actor(kind=ActorKind.CLAUDE, client=Client.CODE))
    numbers, busy = [], 0
    with Store.open(Path(db_path)) as store:
        barrier.wait(timeout=60)
        started = time.perf_counter()
        for index in range(ITEMS_PER_WORKER):
            request = ItemCreate(
                kind=ItemKind.SUBTASK,
                title=f"{os.getpid()}-{index}",
                parent_id=batch_id,
            )
            try:
                numbers.append(create_item(store, project_id, request, ctx)[0].number)
            except sqlite3.OperationalError as exc:
                if exc.sqlite_errorcode & 0xFF != sqlite3.SQLITE_BUSY:
                    raise
                busy += 1
        results.put((numbers, busy, time.perf_counter() - started, os.getpid()))


def test_concurrent_creates_get_unique_contiguous_numbers(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    event_kinds: Callable[[Project], list[tuple[str, str]]],
    spawn_workers: Any,
) -> None:
    """8 processes x 25 subtasks in one batch -> numbers 1..200, no busy errors."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    events_before = len(event_kinds(project))
    args = [(str(store.path), project.id, batch.id)] * WORKERS
    results = spawn_workers(_create_items, args)
    numbers = sorted(n for worker_numbers, *_ in results for n in worker_numbers)
    assert sum(busy for _, busy, *_ in results) == 0
    pids = {pid for *_, pid in results}
    assert len(pids) == WORKERS and os.getpid() not in pids
    assert numbers == list(range(1, WORKERS * ITEMS_PER_WORKER + 1))
    new_events = event_kinds(project)[events_before:]
    assert new_events == [("item", "create")] * (WORKERS * ITEMS_PER_WORKER)
    with store.read() as conn:
        next_number = conn.execute(
            "SELECT next_child_number FROM item WHERE id = ?", (batch.id,)
        ).fetchone()[0]
    assert next_number == WORKERS * ITEMS_PER_WORKER + 1


def test_state_defaults_to_open_and_is_validated(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """New items start open; a named state must exist in the workflow."""
    assert make_item(project, ItemKind.GOAL).state == "open"
    assert make_item(project, ItemKind.GOAL, state="blocked").state == "blocked"
    with pytest.raises(StateError, match="not in the active workflow"):
        make_item(project, ItemKind.GOAL, state="someday")


def test_backlog_items_come_only_from_capture(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """item_create refuses the backlog kind at any level."""
    with pytest.raises(HierarchyError, match="capture"):
        make_item(project, ItemKind.BACKLOG)


def test_parent_must_be_in_the_project(
    project: Project, other_project: Project, make_item: Callable[..., Item]
) -> None:
    """A batch cannot sit under another project's goal."""
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        make_item(project, ItemKind.BATCH, parent_id=foreign.id)


def test_backlog_state_uses_the_backlog_workflow(
    store: Store,
    ctx: WriteContext,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
) -> None:
    """A backlog item accepts open, done and dropped, and nothing else."""
    item = capture_on(work_tree[2])
    with pytest.raises(StateError):
        update_item(store, item.id, 1, ItemUpdate(state="active"), ctx)
    closed, _ = update_item(store, item.id, 1, ItemUpdate(state="dropped"), ctx)
    assert closed.state == "dropped"


def test_unchanged_update_keeps_the_version(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """Setting fields to their current values writes nothing."""
    item = make_item(project, ItemKind.GOAL, title="same")
    assert update_item(store, item.id, 1, ItemUpdate(title="same"), ctx)[0] == item


def test_awaited_decision_is_checked(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """An unknown awaited decision is refused before any write."""
    item = make_item(project, ItemKind.GOAL)
    with pytest.raises(NotFoundError):
        update_item(store, item.id, 1, ItemUpdate(awaiting_decision_id=99), ctx)
    with store.read() as conn:
        assert require_item(conn, item.id).version == 1


def test_missing_item(store: Store) -> None:
    """Unknown ids raise NotFoundError."""
    with pytest.raises(NotFoundError):
        get_item(store, 12345)
