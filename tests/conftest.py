"""
Shared fixtures: a fresh database per test (always under tmp_path, never
the user's real data), standard actors, registered projects and factories.
"""

import multiprocessing
import os
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.session.client import Client
from xoot.models.session.session import Session
from xoot.models.session.session_start import SessionStart
from xoot.repositories.event import event_db
from xoot.services.item_service import create_item
from xoot.services.project_service import register_project
from xoot.services.session_service import start_session
from xoot.store.store import Store

WORKER_TIMEOUT_S = 180

type SpawnWorkers = Callable[
    [Callable[..., None], Sequence[tuple[Any, ...]]], list[Any]
]


@pytest.fixture(name="db_path")
def fixture_db_path(tmp_path: Path) -> Path:
    """A database path inside the test's private tmp directory."""
    return tmp_path / "data" / "xoot.db"


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
    """A write context for the user, outside any session."""
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


@pytest.fixture(name="make_item")
def fixture_make_item(store: Store, ctx: WriteContext) -> Callable[..., Item]:
    """Factory: create an item of a kind in a project, extra fields optional."""

    def make(project: Project, kind: ItemKind, **fields: Any) -> Item:
        fields.setdefault("title", f"{kind} item")
        return create_item(store, project.id, ItemCreate(kind=kind, **fields), ctx)

    return make


@pytest.fixture(name="make_session")
def fixture_make_session(store: Store, user: Actor) -> Callable[..., Session]:
    """Factory: start a session in a project, optionally with focus items."""

    def make(project: Project, *focus: int) -> Session:
        request = SessionStart(title="session", focus_item_ids=focus)
        return start_session(store, project.id, request, user).session

    return make


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
