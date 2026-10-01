"""
Shared fixtures: a fresh database per test (always under tmp_path, never
the user's real data), standard actors, registered projects and factories.
"""

import multiprocessing
import os
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.event import event_db
from xoot.services.backlog_service import capture
from xoot.services.item_service import create_item, update_item
from xoot.services.project_service import register_project
from xoot.store.migrator import SCHEMA_VERSION
from xoot.store.store import Store

WORKER_TIMEOUT_S = 180

type SpawnWorkers = Callable[
    [Callable[..., None], Sequence[tuple[Any, ...]]], list[Any]
]


@pytest.fixture(name="db_path")
def fixture_db_path(tmp_path: Path) -> Path:
    """A database path inside the test's private tmp directory."""
    return tmp_path / "data" / "xoot.db"


@pytest.fixture(name="newer_database")
def fixture_newer_database(db_path: Path) -> Callable[[], int]:
    """Factory: create the test database, then stamp it one schema version
    past SCHEMA_VERSION, as a newer xoot would leave it. Returns that version."""

    def stamp() -> int:
        if not db_path.exists():
            Store.open(db_path).close()
        newer = SCHEMA_VERSION + 1
        raw = sqlite3.connect(db_path)
        try:
            # PRAGMA takes no bound parameters; newer is an int.
            raw.execute(f"PRAGMA user_version = {newer}")
        finally:
            raw.close()
        return newer

    return stamp


@pytest.fixture(name="foreign_event")
def fixture_foreign_event(db_path: Path) -> Callable[[Item], int]:
    """Factory: append an event on an item whose client this code does not
    know, as a newer xoot would write it. The CHECK constraint is bypassed
    on a raw connection of the test database only. Returns the event id."""

    def plant(item: Item) -> int:
        raw = sqlite3.connect(db_path, autocommit=True)
        try:
            raw.execute("PRAGMA ignore_check_constraints = ON")
            row = raw.execute(
                "INSERT INTO event (project_id, entity_type, entity_id, action, "
                "actor_kind, client, before, after, created_at) "
                "SELECT project_id, entity_type, entity_id, action, actor_kind, "
                "'telepathy', before, after, created_at FROM event "
                "WHERE entity_type = 'item' AND entity_id = ? ORDER BY id LIMIT 1 "
                "RETURNING id",
                (item.id,),
            ).fetchone()
        finally:
            raw.close()
        return int(row[0])

    return plant


@pytest.fixture(name="open_umask")
def fixture_open_umask() -> Iterator[None]:
    """Run with umask 000, so only explicit modes can produce 0700/0600."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.fixture(name="store")
def fixture_store(db_path: Path) -> Iterator[Store]:
    """An opened, migrated store on a fresh database."""
    with Store.open(db_path) as opened:
        yield opened


@pytest.fixture(name="user")
def fixture_user() -> Actor:
    """The user, writing through the CLI."""
    return Actor(kind=ActorKind.USER, client=Client.CLI)


@pytest.fixture(name="claude")
def fixture_claude() -> Actor:
    """Claude, writing through Claude Code."""
    return Actor(kind=ActorKind.CLAUDE, client=Client.CODE)


@pytest.fixture(name="ctx")
def fixture_ctx(user: Actor) -> WriteContext:
    """A write context for the user, through the CLI."""
    return WriteContext(actor=user)


@pytest.fixture(name="project")
def fixture_project(store: Store, user: Actor) -> Project:
    """A registered project "xoot" with one alias and one path."""
    registration = ProjectRegistration(
        key_prefix="xoot", name="xoot", aliases=("xo",), paths=("/work/xoot",)
    )
    return register_project(store, registration, user)


@pytest.fixture(name="other_project")
def fixture_other_project(store: Store, user: Actor) -> Project:
    """A second project, for cross-project checks."""
    return register_project(
        store, ProjectRegistration(key_prefix="nova", name="nova"), user
    )


@pytest.fixture(name="extended_definition")
def fixture_extended_definition() -> WorkflowDefinition:
    """The default workflow plus an active goal state "review": a real change
    that strands no item, since an identical import is a no-op."""
    data = WorkflowDefinition.default().model_dump()
    data["kinds"][ItemKind.GOAL]["states"] += (
        {"name": "review", "category": Category.ACTIVE},
    )
    return WorkflowDefinition.model_validate(data)


@pytest.fixture(name="make_item")
def fixture_make_item(store: Store, ctx: WriteContext) -> Callable[..., Item]:
    """Factory: create an item of a kind in a project, extra fields optional."""

    def make(project: Project, kind: ItemKind, **fields: Any) -> Item:
        fields.setdefault("title", f"{kind} item")
        return create_item(store, project.id, ItemCreate(kind=kind, **fields), ctx)[0]

    return make


@pytest.fixture(name="capture_on")
def fixture_capture_on(store: Store, ctx: WriteContext) -> Callable[..., Item]:
    """Factory: capture a backlog item found on an item."""

    def make(found_on: Item, title: str = "found work", body: str = "why") -> Item:
        draft = ItemDraft(title=title, body=body)
        return capture(store, found_on.project_id, found_on.id, draft, ctx)[0]

    return make


@pytest.fixture(name="set_state")
def fixture_set_state(store: Store, ctx: WriteContext) -> Callable[..., Item]:
    """Factory: move an item to a state at its current version."""

    def move(item: Item, state: str) -> Item:
        with store.read() as conn:
            current = conn.execute(
                "SELECT version FROM item WHERE id = ?", (item.id,)
            ).fetchone()[0]
        return update_item(store, item.id, current, ItemUpdate(state=state), ctx)[0]

    return move


@pytest.fixture(name="work_tree")
def fixture_work_tree(
    project: Project, make_item: Callable[..., Item]
) -> tuple[Item, Item, Item, Item]:
    """goal-1, its batch goal-1/batch-1, and two subtasks in that batch."""
    goal = make_item(project, ItemKind.GOAL, title="goal")
    batch = make_item(project, ItemKind.BATCH, title="batch", parent_id=goal.id)
    first = make_item(project, ItemKind.SUBTASK, title="one", parent_id=batch.id)
    second = make_item(project, ItemKind.SUBTASK, title="two", parent_id=batch.id)
    return goal, batch, first, second


@pytest.fixture(name="event_kinds")
def fixture_event_kinds(store: Store) -> Callable[[Project], list[tuple[str, str]]]:
    """Factory: a project's events as (entity_type, action) pairs, in order."""

    def kinds(project: Project) -> list[tuple[str, str]]:
        with store.read() as conn:
            events = event_db.list_for_project(conn, project.id)
        return [(event.entity_type.value, event.action.value) for event in events]

    return kinds


@pytest.fixture(name="row_counts")
def fixture_row_counts(store: Store) -> Callable[[], dict[str, int]]:
    """Factory: the row count of every table, to prove a call wrote nothing."""

    def counts() -> dict[str, int]:
        with store.read() as conn:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table'"
                )
            ]
            # Table names come from sqlite_schema itself, not from input.
            return {
                table: conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                for table in tables
            }

    return counts


@pytest.fixture(name="spawn_workers")
def fixture_spawn_workers() -> SpawnWorkers:
    """
    Factory: run a module-level target in real spawned processes.

    Each worker gets its own args plus a shared barrier (so they start
    together) and a result queue it must put exactly one value on. Workers
    are joined and their exit codes checked before results are read, so a
    crashed worker fails the test at once instead of hanging on the queue.
    """

    def run(
        target: Callable[..., None], arg_sets: Sequence[tuple[Any, ...]]
    ) -> list[Any]:
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(len(arg_sets))
        results = context.Queue()
        workers = [
            context.Process(target=target, args=(*args, barrier, results))
            for args in arg_sets
        ]
        for worker in workers:
            worker.start()
        try:
            for worker in workers:
                worker.join(timeout=WORKER_TIMEOUT_S)
            assert [worker.exitcode for worker in workers] == [0] * len(workers)
            return [results.get(timeout=10) for _ in workers]
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.kill()

    return run
