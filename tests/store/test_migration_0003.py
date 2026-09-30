"""
Migration 0003: the event table is rebuilt with every row, id and trigger;
'dashboard' becomes a client; pending confirm tokens are purged.
"""

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.item_service import create_item, update_item
from xoot.services.project_service import register_project
from xoot.services.redaction_service import redact_field
from xoot.store import migrator
from xoot.store.backup import backup_path
from xoot.store.connection import connect
from xoot.store.migrator import load_migrations, migrate, user_version
from xoot.store.store import Store

PROCESSES = 3
BEFORE_DASHBOARD = [client for client in Client if client is not Client.DASHBOARD]
ACTORS = [
    Actor(kind=ActorKind.USER if c is Client.CLI else ActorKind.CLAUDE, client=c)
    for c in BEFORE_DASHBOARD
]
REBUILD_MARK = "ALTER TABLE event RENAME TO event_pre_0003"
LIVE = "2999-01-01T00:00:00.000000Z"
USED = "2026-01-01T00:04:00.000000Z"
EXPIRED = "2026-01-01T00:05:00.000000Z"


def _baseline(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A database at version 2 with events from every pre-0003 client."""
    baseline = load_migrations()[:1]
    with monkeypatch.context() as patch:
        patch.setattr(migrator, "load_migrations", lambda: baseline)
        with Store.open(db_path) as store:
            assert user_version(store.conn) == 2
            owner = Actor(kind=ActorKind.USER, client=Client.CLI)
            project = register_project(
                store,
                ProjectRegistration(key_prefix="xoot", name="xoot", aliases=("xo",)),
                owner,
            )
            for actor in ACTORS:
                item, _ = create_item(
                    store,
                    project.id,
                    ItemCreate(kind=ItemKind.GOAL, title=f"by {actor.client}"),
                    WriteContext(actor=actor),
                )
                update_item(
                    store,
                    item.id,
                    item.version,
                    ItemUpdate(body="moved on"),
                    WriteContext(actor=actor),
                )
            redact_field(store, "item", item.id, "title", owner)
            with store.write() as conn:
                for name, used_at in (("a", None), ("b", USED)):
                    expires = LIVE if used_at is None else EXPIRED
                    conn.execute(
                        "INSERT INTO confirm_token (token_sha256, project_id, tool, "
                        "args_sha256, plan_sha256, expires_at, used_at) "
                        "VALUES (?, ?, 'backlog_push', ?, ?, ?, ?)",
                        (name * 64, project.id, "c" * 64, "d" * 64, expires, used_at),
                    )


def _snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    """Every event row, the event AUTOINCREMENT mark, all triggers and event indexes."""
    queries = {
        "rows": "SELECT * FROM event ORDER BY id",
        "seq": "SELECT seq FROM sqlite_sequence WHERE name = 'event'",
        "triggers": "SELECT name, tbl_name, sql FROM sqlite_schema "
        "WHERE type = 'trigger' ORDER BY name",
        "indexes": "SELECT name, sql FROM sqlite_schema "
        "WHERE type = 'index' AND tbl_name = 'event' ORDER BY name",
    }
    return {
        name: [tuple(row) for row in conn.execute(sql)] for name, sql in queries.items()
    }


def _raw(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _migrate_traced(db_path: str, barrier: Any, results: Any) -> None:
    """Spawned worker: migrate the shared database, report whether it rebuilt."""
    conn = connect(Path(db_path))
    traced: list[str] = []
    conn.set_trace_callback(traced.append)
    try:
        barrier.wait(timeout=60)
        version = migrate(conn, db_path=Path(db_path))
    finally:
        conn.close()
    results.put((version, any(REBUILD_MARK in sql for sql in traced)))


def _open_store(db_path: str, barrier: Any, results: Any) -> None:
    """Spawned worker: open the shared database through Store.open."""
    barrier.wait(timeout=60)
    with Store.open(Path(db_path)) as store:
        results.put(user_version(store.conn))


def test_every_row_id_and_trigger_survives(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rows, ids, the id high-water mark, triggers and indexes are unchanged."""
    _baseline(db_path, monkeypatch)
    raw = _raw(db_path)
    try:
        before = _snapshot(raw)
        clients = {row[0] for row in raw.execute("SELECT client FROM event")}
    finally:
        raw.close()
    assert clients == {str(client) for client in BEFORE_DASHBOARD}
    assert len(before["rows"]) > len(ACTORS) and before["triggers"]
    with Store.open(db_path) as store:
        assert user_version(store.conn) == 3
        after = _snapshot(store.conn)
        tokens = store.conn.execute("SELECT count(*) FROM confirm_token").fetchone()
    assert after == before
    assert [row[0] for row in after["rows"]] == [row[0] for row in before["rows"]]
    assert tokens[0] == 0
    copy = sqlite3.connect(backup_path(db_path, 3))
    try:
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 2
        assert copy.execute("SELECT count(*) FROM event").fetchone()[0] == len(
            before["rows"]
        )
    finally:
        copy.close()


def test_the_rebuilt_log_is_still_append_only(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both triggers fire; 'dashboard' is accepted and unknown clients are not."""
    _baseline(db_path, monkeypatch)
    Store.open(db_path).close()
    raw = _raw(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("DELETE FROM event WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("UPDATE event SET client = 'cli' WHERE id = 1")
        insert = (
            "INSERT INTO event (project_id, entity_type, entity_id, action, "
            "actor_kind, client, after, created_at) VALUES (1, 'project', 1, "
            "'update', 'user', ?, '{}', '2026-09-30T00:00:00.000000Z')"
        )
        raw.execute(insert, ("dashboard",))
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            raw.execute(insert, ("browser",))
        max_id = raw.execute("SELECT max(id) FROM event").fetchone()[0]
        seq = raw.execute("SELECT seq FROM sqlite_sequence WHERE name = 'event'")
        assert seq.fetchone()[0] == max_id
    finally:
        raw.close()


def test_a_fresh_database_gets_the_same_triggers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new file reaches 3 with the 0002 trigger text and takes dashboard writes."""
    baseline = load_migrations()[:1]
    with monkeypatch.context() as patch:
        patch.setattr(migrator, "load_migrations", lambda: baseline)
        with Store.open(tmp_path / "v2.db") as old:
            expected = _snapshot(old.conn)["triggers"]
    with Store.open(tmp_path / "fresh.db") as store:
        assert user_version(store.conn) == 3
        assert _snapshot(store.conn)["triggers"] == expected
        dashboard = Actor(kind=ActorKind.USER, client=Client.DASHBOARD)
        project = register_project(
            store, ProjectRegistration(key_prefix="xoot", name="xoot"), dashboard
        )
        clients = store.conn.execute(
            "SELECT DISTINCT client FROM event WHERE project_id = ?", (project.id,)
        ).fetchall()
    assert [row[0] for row in clients] == ["dashboard"]
    assert not list(tmp_path.glob("fresh.db.pre-v*"))


def test_three_processes_migrate_exactly_once(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, spawn_workers: Any
) -> None:
    """Racing openers of an un-migrated database: one rebuild, no error."""
    _baseline(db_path, monkeypatch)
    raw = _raw(db_path)
    try:
        before = _snapshot(raw)
    finally:
        raw.close()
    outcomes = spawn_workers(_migrate_traced, [(str(db_path),)] * PROCESSES)
    assert [version for version, _ in outcomes] == [3] * PROCESSES
    assert sum(1 for _, rebuilt in outcomes if rebuilt) == 1
    assert [p.name for p in db_path.parent.glob("*.pre-v*")] == ["xoot.db.pre-v3"]
    with Store.open(db_path) as store:
        assert _snapshot(store.conn) == before


def test_three_store_opens_all_succeed(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, spawn_workers: Any
) -> None:
    """The dashboard's per-request Store.open, three at once, never fails."""
    _baseline(db_path, monkeypatch)
    versions = spawn_workers(_open_store, [(str(db_path),)] * PROCESSES)
    assert versions == [3] * PROCESSES
