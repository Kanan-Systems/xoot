"""Tool errors are safe: fixed reasons, field locations, no SQL, no input values."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.services.item_service import update_item
from xoot.store.store import Store

type Corpus = list[tuple[str, dict[str, Any]]]
type Tree = tuple[Item, Item, Item, Item]

SQL = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|FROM|WHERE|TABLE|CONSTRAINT|PRAGMA)\b"
)
MARKER = "MARKER"


@pytest.fixture(name="corpus")
def fixture_corpus(
    work_tree: Tree,
    other_project: Project,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> Corpus:
    """Calls that must fail, most of them carrying MARKER or SQL in their input."""
    goal, batch, first, _ = work_tree
    foreign = make_item(other_project, ItemKind.GOAL)
    on_goal = capture_on(goal)
    update = {"project": "xo", "key": goal.key, "expected_version": 1}
    return [
        ("item_get", {"project": "xo", "key": f"x'; DROP TABLE item; --{MARKER}"}),
        ("brief_get", {"project": f"SELECT * FROM project {MARKER}"}),
        (
            "capture",
            {"project": "xo", "found_on": first.key, "title": MARKER + "x" * 200,
             "body": ""},
        ),  # fmt: skip
        (
            "capture",
            {"project": "xo", "found_on": first.key, "title": f"a\x00{MARKER}",
             "body": ""},
        ),  # fmt: skip
        ("backlog_cover", {"project": "xo", "key": on_goal.key}),
        ("item_update", {**update, "changes": {"state": f"bogus_{MARKER.lower()}"}}),
        ("item_update", {**update, "changes": {f"extra_{MARKER}": 1}}),
        ("item_update", {**update, "expected_version": MARKER, "changes": {}}),
        ("item_create", {"project": "xo", "kind": "batch", "title": MARKER}),
        (
            "item_create",
            {"project": "xo", "kind": "batch", "title": "b",
             "parent": f"nova:{foreign.key}"},
        ),  # fmt: skip
        ("item_create", {"project": "xo", "kind": "backlog", "title": MARKER}),
        ("backlog_push", {"project": "xo", "key": batch.key}),
        ("tree_get", {"project": "xo", "depth": 99}),
        (
            "items_create_bulk",
            {"project": "xo", "items": [{"kind": "goal", "title": MARKER}] * 51},
        ),
        (
            "decision_record",
            {"project": "xo", "owner": goal.key, "title": MARKER, "body": "b",
             "status": "superseded"},
        ),  # fmt: skip
        (
            "backlog_push",
            {"project": "xo", "key": on_goal.key, "confirm_token": MARKER},
        ),
    ]


def test_version_conflict_names_fields_and_actors(
    store: Store, ctx: WriteContext, work_tree: Tree, harness: Any
) -> None:
    """A stale expected_version reports the current version, fields and actors."""
    goal = work_tree[0]
    update_item(store, goal.id, 1, ItemUpdate(title="changed", state="active"), ctx)

    async def scenario(client: ClientSession) -> str:
        return await harness.error(
            client,
            "item_update",
            project="xo",
            key=goal.key,
            expected_version=1,
            changes={"title": "mine"},
        )

    message = harness.run(scenario)
    assert "VersionConflictError: goal-1 is at version 2" in message
    assert "changed since your version: state, title" in message
    assert "by: user/cli" in message


@pytest.mark.usefixtures("work_tree")
def test_unknown_keys_are_not_found(harness: Any) -> None:
    """Unknown or malformed keys of every kind read "not found: <key>"."""
    update = {"project": "xo", "expected_version": 1, "changes": {}}

    async def scenario(client: ClientSession) -> list[str]:
        return [
            await harness.error(client, "item_get", project="xo", key="goal-99"),
            await harness.error(client, "item_get", key="xoot:goal-1/batch-7"),
            await harness.error(
                client, "decision_update", key="goal-1/decision-9", **update
            ),
            await harness.error(client, "item_get", project="xo", key="xoot-1"),
            await harness.error(client, "item_get", project="xo", key="goal-1 OR 1=1"),
        ]

    assert harness.run(scenario) == [
        "Error executing tool item_get: not found: goal-99",
        "Error executing tool item_get: not found: xoot:goal-1/batch-7",
        "Error executing tool decision_update: not found: goal-1/decision-9",
        "Error executing tool item_get: not found: malformed key",
        "Error executing tool item_get: not found: malformed key",
    ]


@pytest.mark.usefixtures("work_tree", "other_project")
def test_qualifiers_must_agree(harness: Any) -> None:
    """Mixed qualifiers, or one against the project argument, are refused."""

    async def scenario(client: ClientSession) -> list[str]:
        return [
            await harness.error(client, "item_get", project="xo", key="nova:goal-1"),
            await harness.error(
                client,
                "backlog_cover",
                key="xoot:goal-1/backlog-1",
                batch="nova:goal-1/batch-1",
            ),
        ]

    first, second = harness.run(scenario)
    assert "QualifierError" in first and "another project" in first
    assert "QualifierError" in second and "more than one project" in second


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
    assert "BacklogError" in messages[4] and "name the batch" in messages[4]
    assert "StateError" in messages[5]
    assert messages[6].endswith("invalid arguments: changes.* (extra_forbidden)")
    assert messages[7].endswith("invalid arguments: expected_version (int_type)")
    assert "HierarchyError" in messages[8]
    assert "QualifierError" in messages[9]
    assert "invalid arguments: kind" in messages[10]
    assert "BacklogError" in messages[11] and "not a backlog item" in messages[11]
    assert "ConfirmTokenError: the confirm token is unknown" in messages[15]


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
