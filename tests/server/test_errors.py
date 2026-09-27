"""S6: tool errors are safe: fixed reasons, field locations, no SQL, no input values."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.services.item_service import update_item
from xoot.services.session_close_service import close_session
from xoot.store.store import Store

type Corpus = list[tuple[str, dict[str, Any]]]

SQL = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|FROM|WHERE|TABLE|CONSTRAINT|PRAGMA)\b"
)
MARKER = "MARKER"
SESSION = "xoot-S1"


@pytest.fixture(name="conflicted")
def fixture_conflicted(
    store: Store,
    ctx: WriteContext,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> Item:
    """A goal the user changed after version 1, and an open session."""
    goal = make_item(project, ItemKind.GOAL)
    make_session(project)
    update_item(store, goal.id, 1, ItemUpdate(title="changed", state="active"), ctx)
    return goal


@pytest.fixture(name="goals")
def fixture_goals(
    project: Project, other_project: Project, make_item: Callable[..., Item]
) -> tuple[Item, Item]:
    """A goal in xoot and one in nova."""
    return make_item(project, ItemKind.GOAL), make_item(other_project, ItemKind.GOAL)


@pytest.fixture(name="sessions")
def fixture_sessions(
    store: Store, user: Actor, project: Project, make_session: Callable[..., Session]
) -> None:
    """xoot-S1 open, xoot-S2 closed."""
    make_session(project)
    close_session(store, make_session(project).id, SessionClose(), user)


@pytest.fixture(name="corpus")
def fixture_corpus(goals: tuple[Item, Item], sessions: None) -> Corpus:
    """Calls that must fail, most of them carrying MARKER or SQL in their input."""
    assert sessions is None
    goal, foreign = goals
    update = {"session": SESSION, "key": goal.key, "expected_version": 1}
    return [
        ("item_get", {"key": f"x'; DROP TABLE item; --{MARKER}"}),
        ("brief_get", {"project": f"SELECT * FROM project {MARKER}"}),
        ("capture", {"session": SESSION, "title": MARKER + "x" * 200}),
        ("capture", {"session": SESSION, "title": f"a\x00{MARKER}"}),
        ("capture", {"session": "xoot-S2", "title": MARKER}),
        ("item_update", {**update, "changes": {"state": f"bogus_{MARKER.lower()}"}}),
        ("item_update", {**update, "changes": {f"extra_{MARKER}": 1}}),
        ("item_update", {**update, "expected_version": MARKER, "changes": {}}),
        ("item_create", {"session": SESSION, "kind": "batch", "title": MARKER}),
        (
            "item_create",
            {"session": SESSION, "kind": "batch", "title": "b", "parent": foreign.key},
        ),
        ("session_close", {"session": SESSION, "dispositions": {goal.key: MARKER}}),
        (
            "session_close",
            {"session": SESSION, "dispositions": {}, "confirm_token": MARKER},
        ),
        ("tree_get", {"project": "xo", "depth": 99}),
        (
            "items_create_bulk",
            {"session": SESSION, "items": [{"kind": "subtask", "title": MARKER}] * 51},
        ),
        (
            "decision_record",
            {"session": SESSION, "title": MARKER, "body": "b", "status": "superseded"},
        ),
    ]


def test_version_conflict_names_fields_and_actors(
    conflicted: Item, harness: Any
) -> None:
    """A stale expected_version reports the current version, fields and actors."""

    async def scenario(client: ClientSession) -> str:
        return await harness.error(
            client,
            "item_update",
            session=SESSION,
            key=conflicted.key,
            expected_version=1,
            changes={"title": "mine"},
        )

    message = harness.run(scenario)
    assert "VersionConflictError: xoot-1 is at version 2" in message
    assert "changed since your version: state, title" in message
    assert "by: user/cli" in message


def test_unknown_keys_are_not_found(
    project: Project, make_session: Callable[..., Session], harness: Any
) -> None:
    """Unknown or malformed keys of every kind read "not found: <key>"."""
    make_session(project)
    update = {"session": SESSION, "expected_version": 1, "changes": {}}

    async def scenario(client: ClientSession) -> list[str]:
        return [
            await harness.error(client, "item_get", key="xoot-99"),
            await harness.error(client, "item_get", key="nova-1"),
            await harness.error(client, "capture", session="xoot-S9", title="t"),
            await harness.error(client, "decision_update", key="xoot-D9", **update),
            await harness.error(client, "item_get", key="xoot-D1"),
            await harness.error(client, "item_get", key="xoot-1 OR 1=1"),
        ]

    assert harness.run(scenario) == [
        "Error executing tool item_get: not found: xoot-99",
        "Error executing tool item_get: not found: nova-1",
        "Error executing tool capture: not found: xoot-S9",
        "Error executing tool decision_update: not found: xoot-D9",
        "Error executing tool item_get: not found: xoot-D1",
        "Error executing tool item_get: not found: malformed key",
    ]


def test_forced_failures_leak_nothing(corpus: Corpus, harness: Any) -> None:
    """Every forced failure in the corpus names no SQL and echoes no input."""

    async def scenario(client: ClientSession) -> list[str]:
        return [await harness.error(client, name, **args) for name, args in corpus]

    messages = harness.run(scenario)
    assert len(messages) == len(corpus)
    for message in messages:
        assert not SQL.search(message), message
        assert "sqlite" not in message.lower(), message
        assert MARKER not in message and MARKER.lower() not in message, message
    assert messages[2].endswith("invalid arguments: title (string_too_long)")
    assert "SessionStateError" in messages[4] and "StateError" in messages[5]
    assert messages[6].endswith("invalid arguments: changes.* (extra_forbidden)")
    assert messages[7].endswith("invalid arguments: expected_version (int_type)")
    assert "HierarchyError" in messages[8] and "CrossProjectError" in messages[9]
    assert messages[10].endswith("invalid arguments: dispositions.* (enum)")
    assert "ConfirmTokenError: the confirm token is unknown" in messages[11]


def test_store_errors_hide_the_path(
    db_path: Path, project: Project, harness: Any
) -> None:
    """An unsafe database file is refused with a reason that names no path."""
    assert project.key_prefix == "xoot"
    db_path.chmod(0o644)

    async def scenario(client: ClientSession) -> str:
        return await harness.error(client, "projects_list")

    message = harness.run(scenario)
    assert "UnsafePathError: the database path failed" in message
    assert str(db_path.parent) not in message
