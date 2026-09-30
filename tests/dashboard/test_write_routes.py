"""
Every write route on a seeded tmp database: it succeeds, it is recorded as
user/dashboard, it refuses a stale version and invalid input without
writing, and its two-phase tokens are single-use, short-lived and bound to
the dashboard client.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import TestClient

from xoot.dashboard.views.write_views import MOVE_TOOL, PUSH_TOOL, UPDATE_TOOL
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.server.confirm import args_digest
from xoot.services import confirm_service
from xoot.services.backlog_push_service import preview_push
from xoot.services.confirm_service import TOKEN_TTL, issue_token
from xoot.services.project_service import add_alias
from xoot.services.subtree_service import preview_drop, preview_reparent
from xoot.store.store import Store

BASE = "/api/v1/projects/xoot"
CODE = Actor(kind=ActorKind.CLAUDE, client=Client.CODE)

# Every write route with a body it accepts on the seeded project, the status
# it answers with, and a body its model refuses.
ROUTES: list[tuple[str, str, dict[str, Any], int, dict[str, Any]]] = [
    ("POST", "/items", {"kind": "goal", "title": "g"}, 201,
     {"kind": "backlog", "title": "g"}),
    ("PATCH", "/items/goal-1/batch-1/subtask-1", {"expected_version": 2, "title": "t"},
     200, {"expected_version": 2}),
    ("POST", "/moves", {"key": "goal-1/batch-1/subtask-1", "parent": "goal-1/batch-2",
     "expected_version": 2}, 200, {"key": "goal-1/batch-1/subtask-1"}),
    ("POST", "/backlog", {"found_on": "goal-1", "title": "f", "body": "why"}, 201,
     {"found_on": "goal-1", "title": "f"}),
    ("POST", "/backlog/covers", {"key": "goal-1/batch-1/backlog-1"}, 200,
     {"key": "goal-1/batch-1/backlog-1", "extra": 1}),
    ("POST", "/decisions", {"owner": "goal-1", "title": "d"}, 201,
     {"owner": "goal-1", "title": "x" * 201}),
    ("PATCH", "/decisions/goal-1/batch-1/decision-1", {"expected_version": 1,
     "status": "deferred"}, 200, {"expected_version": 1, "status": "superseded"}),
    ("PATCH", "", {"name": "renamed", "alias": "renamed"}, 200,
     {"key_prefix": "other"}),
]  # fmt: skip
IDS = [f"{method} {path or '/'}" for method, path, *_ in ROUTES]


def _call(client: TestClient, method: str, path: str, body: Any, origin: str) -> Any:
    return client.request(
        method,
        f"{BASE}{path}",
        content=json.dumps(body),
        headers={"origin": origin, "content-type": "application/json"},
    )


def _events(store: Store) -> list[tuple[int, str, str]]:
    with store.read() as conn:
        rows = conn.execute("SELECT id, actor_kind, client FROM event ORDER BY id")
        return [tuple(row) for row in rows]


@pytest.fixture(name="post")
def fixture_post(client: TestClient, launch: Any, seeded: Any) -> Any:
    """Send a write from the served origin, on the seeded project plus goal-1/batch-2
    and goal-2."""
    assert seeded.decision_key == "goal-1/batch-1/decision-1"

    def send(method: str, path: str, body: Any) -> Any:
        return _call(client, method, path, body, launch.origin)

    for body in (
        {"kind": "batch", "title": "b2", "parent": "goal-1"},
        {"kind": "goal", "title": "g2"},
    ):
        created = send("POST", "/items", body)
        assert created.status_code == 201, created.text
    return send


@pytest.mark.parametrize(("method", "path", "body", "status", "_bad"), ROUTES, ids=IDS)
def test_each_write_succeeds_as_user_dashboard(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    post: Any,
    method: str,
    path: str,
    body: dict[str, Any],
    status: int,
    _bad: dict[str, Any],
) -> None:
    """The write lands; its own events are user/dashboard, the engine's system/dashboard."""
    before = _events(store)
    response = post(method, path, body)
    assert response.status_code == status, response.text
    new = _events(store)[len(before) :]
    assert new
    assert {client for _, _, client in new} == {"dashboard"}
    assert {kind for _, kind, _ in new} <= {"user", "system"}
    assert any(kind == "user" for _, kind, _ in new)


@pytest.mark.parametrize(("method", "path", "_body", "_status", "bad"), ROUTES, ids=IDS)
def test_invalid_input_is_422_and_writes_nothing(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    post: Any,
    method: str,
    path: str,
    _body: dict[str, Any],
    _status: int,
    bad: dict[str, Any],
) -> None:
    """A body the model refuses answers {error, message, details} with no write."""
    before = _events(store)
    response = post(method, path, bad)
    assert response.status_code == 422, response.text
    assert set(response.json()) == {"error", "message", "details"}
    assert response.json()["error"] == "ValidationError"
    assert _events(store) == before


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", "", "null", '"goal"'])
def test_a_body_that_is_not_an_object_is_422(
    client: TestClient, launch: Any, store: Store, post: Any, raw: str
) -> None:
    """Malformed JSON and non-object bodies are validation failures."""
    assert post
    before = _events(store)
    response = client.post(
        f"{BASE}/items",
        content=raw,
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "ValidationError"
    assert _events(store) == before


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/items/goal-1/batch-1/subtask-1", {"expected_version": 1, "title": "t"}),
        ("POST", "/moves", {"key": "goal-1/batch-1/subtask-1",
         "parent": "goal-1/batch-2", "expected_version": 1}),
        ("PATCH", "/decisions/goal-1/batch-1/decision-1",
         {"expected_version": 9, "title": "t"}),
    ],
)  # fmt: skip
def test_a_stale_version_is_409_with_details(
    store: Store, post: Any, method: str, path: str, body: dict[str, Any]
) -> None:
    """The conflict names the key, the current version, what changed and who."""
    before = _events(store)
    response = post(method, path, body)
    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["error"] == "VersionConflictError"
    details = payload["details"]
    assert set(details) == {"key", "current_version", "changed_fields", "actors"}
    assert details["current_version"] != body["expected_version"]
    assert all(set(actor) == {"kind", "client"} for actor in details["actors"])
    assert _events(store) == before


def test_the_subtask_conflict_names_the_state_change(post: Any) -> None:
    """The seeded subtask went to done at version 2, by user/cli."""
    response = post(
        "PATCH", "/items/goal-1/batch-1/subtask-1", {"expected_version": 1, "body": "x"}
    )
    assert response.json()["details"] == {
        "key": "goal-1/batch-1/subtask-1",
        "current_version": 2,
        "changed_fields": ["state"],
        "actors": [{"kind": "user", "client": "cli"}],
    }


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/items/goal-99", {"expected_version": 1, "title": "t"}),
        ("POST", "/items", {"kind": "batch", "title": "b", "parent": "goal-9"}),
        ("POST", "/backlog", {"found_on": "goal-9", "title": "t", "body": "b"}),
        (
            "PATCH",
            "/decisions/goal-1/decision-9",
            {"expected_version": 1, "title": "t"},
        ),
        ("POST", "/backlog/pushes", {"key": "goal-1/backlog-9"}),
    ],
)
def test_missing_records_are_404(post: Any, method: str, path: str, body: Any) -> None:
    """A key that names nothing is a 404."""
    response = post(method, path, body)
    assert response.status_code == 404, response.text
    assert response.json()["error"] == "NotFoundError"


def test_an_unknown_project_is_404(client: TestClient, launch: Any, post: Any) -> None:
    """A prefix that names no project is a 404 on a write too."""
    assert post
    response = client.patch(
        "/api/v1/projects/nope/items/goal-1",
        content=json.dumps({"expected_version": 1, "title": "t"}),
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"] == "NotFoundError"


def test_an_alias_collision_is_409(
    post: Any, store: Store, other_project: Project
) -> None:
    """Another project's prefix or an alias already held are duplicates."""
    assert other_project.key_prefix == "nova"
    response = post("PATCH", "", {"alias": "nova"})
    assert response.status_code == 409
    assert response.json()["error"] == "DuplicateError"
    with store.read() as conn:
        taken = conn.execute(
            "SELECT count(*) FROM project_alias WHERE alias = 'nova'"
        ).fetchone()[0]
    assert taken == 0
    assert post("PATCH", "", {"alias": "xo"}).status_code == 409


def test_the_prefix_cannot_be_renamed(post: Any, client: TestClient) -> None:
    """key_prefix is not a field of the rename; the prefix and URLs stay."""
    assert post("PATCH", "", {"key_prefix": "zz"}).status_code == 422
    assert client.get(f"{BASE}/brief").status_code == 200


def test_manual_done_with_open_children_is_422(post: Any) -> None:
    """The service guard answers 422 with the open keys in details."""
    response = post("PATCH", "/items/goal-1", {"expected_version": 1, "state": "done"})
    assert response.status_code == 422
    assert response.json()["error"] == "OpenChildrenError"
    assert response.json()["details"] == {
        "key": "goal-1",
        "open_keys": ["goal-1/batch-1", "goal-1/batch-2"],
    }


def test_a_plan_over_the_cap_is_422(post: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The plan-size refusal carries the root, size and cap."""
    from xoot.services import plan_cap  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(plan_cap, "MAX_PLAN_ITEMS", 1)
    response = post(
        "POST",
        "/moves",
        {"key": "goal-1/batch-1", "parent": "goal-2", "expected_version": 1},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "PlanSizeError"
    assert response.json()["details"]["cap"] == 1


# The two-phase writes: a body that previews, and the tool its token is for.
TWO_PHASE: list[tuple[str, str, dict[str, Any], str]] = [
    ("POST", "/backlog/pushes", {"key": "goal-1/batch-1/backlog-1"}, PUSH_TOOL),
    ("POST", "/moves", {"key": "goal-1/batch-1", "parent": "goal-2",
     "expected_version": 1}, MOVE_TOOL),
    ("PATCH", "/items/goal-1/batch-1", {"expected_version": 1, "state": "dropped"},
     UPDATE_TOOL),
]  # fmt: skip
TWO_IDS = ["push", "move", "drop"]


@pytest.mark.parametrize(("method", "path", "body", "_tool"), TWO_PHASE, ids=TWO_IDS)
def test_preview_then_apply_and_no_replay(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    post: Any,
    method: str,
    path: str,
    body: dict[str, Any],
    _tool: str,
) -> None:
    """The preview writes nothing; the token applies once; a replay is 409."""
    before = _events(store)
    preview = post(method, path, body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["phase"] == "preview"
    assert _events(store) == before
    token = preview.json()["confirm_token"]
    applied = post(method, path, {**body, "confirm_token": token})
    assert applied.status_code == 200, applied.text
    assert applied.json()["phase"] == "applied"
    assert {c for _, _, c in _events(store)[len(before) :]} == {"dashboard"}
    after = _events(store)
    replay = post(method, path, {**body, "confirm_token": token})
    assert replay.status_code == 409, replay.text
    assert replay.json()["error"] == "ConfirmTokenError"
    assert _events(store) == after


@pytest.mark.parametrize(("method", "path", "body", "tool"), TWO_PHASE, ids=TWO_IDS)
def test_a_token_issued_to_another_client_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    post: Any,
    project: Project,
    method: str,
    path: str,
    body: dict[str, Any],
    tool: str,
) -> None:
    """Same tool, arguments and plan, issued to claude/code: 409, nothing written."""
    plan = _plan(store, path, body)
    key = {"key": path.removeprefix("/items/")} if method == "PATCH" else {}
    digest = args_digest({"prefix": "xoot", **key, **body})
    token = issue_token(store, project.id, tool, digest, plan, actor=CODE)
    before = _events(store)
    response = post(method, path, {**body, "confirm_token": token})
    assert response.status_code == 409, response.text
    assert "another client" in response.json()["message"]
    assert _events(store) == before
    with store.read() as conn:
        used = conn.execute("SELECT used_at FROM confirm_token").fetchall()
    assert [row[0] for row in used] == [None]


@pytest.mark.parametrize(("method", "path", "body", "_tool"), TWO_PHASE, ids=TWO_IDS)
def test_an_expired_token_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    post: Any,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, Any],
    _tool: str,
) -> None:
    """Once the TTL has passed the apply is 409 and writes nothing."""
    token = post(method, path, body).json()["confirm_token"]
    later = datetime.now(UTC) + TOKEN_TTL
    monkeypatch.setattr(
        confirm_service, "datetime", SimpleNamespace(now=lambda tz: later)
    )
    before = _events(store)
    response = post(method, path, {**body, "confirm_token": token})
    assert response.status_code == 409
    assert "expired" in response.json()["message"]
    assert _events(store) == before


def test_a_token_is_bound_to_its_body(post: Any) -> None:
    """A token for one push does not apply another call's arguments."""
    captured = post(
        "POST", "/backlog", {"found_on": "goal-1/batch-2", "title": "t", "body": "b"}
    )
    other_key = captured.json()["item"]["key"]
    body = {"key": "goal-1/batch-1/backlog-1"}
    token = post("POST", "/backlog/pushes", body).json()["confirm_token"]
    other = post("POST", "/backlog/pushes", {"key": other_key, "confirm_token": token})
    assert other.status_code == 409
    assert "does not match these arguments" in other.json()["message"]


def test_a_childless_drop_and_move_apply_at_once(post: Any) -> None:
    """Without children there is no preview, as with MCP."""
    dropped = post(
        "PATCH", "/items/goal-2", {"expected_version": 1, "state": "dropped"}
    )
    assert dropped.status_code == 200, dropped.text
    assert (dropped.json()["mode"], dropped.json()["phase"]) == ("update", "applied")
    moved = post(
        "POST",
        "/moves",
        {
            "key": "goal-1/batch-1/subtask-1",
            "parent": "goal-1/batch-2",
            "expected_version": 2,
        },
    )
    assert moved.status_code == 200, moved.text
    assert (moved.json()["mode"], moved.json()["phase"]) == ("reparent", "applied")


def _plan(store: Store, path: str, body: dict[str, Any]) -> str:
    """The plan digest the route's own preview would show."""
    with store.read() as conn:
        ids = dict(conn.execute("SELECT key, id FROM item").fetchall())
    if path == "/backlog/pushes":
        return preview_push(store, ids[body["key"]]).plan_sha256
    if path == "/moves":
        return preview_reparent(
            store, ids[body["key"]], ids[body["parent"]]
        ).plan_sha256
    return preview_drop(store, ids["goal-1/batch-1"], "dropped").plan_sha256


@pytest.mark.parametrize("alias", ["nv", "nova"])
def test_a_taken_alias_names_the_alias_never_the_holder(
    store: Store, post: Any, other_project: Project, ctx: WriteContext, alias: str
) -> None:
    """Another project's alias or prefix: the message names only the alias."""
    add_alias(store, other_project.id, "nv", ctx)
    before = _events(store)
    response = post("PATCH", "", {"name": "renamed", "alias": alias})
    assert response.status_code == 409
    assert response.json() == {
        "error": "DuplicateError",
        "message": f"alias '{alias}' is already used by another project",
        "details": {"alias": alias},
    }
    text = response.text.replace(f"'{alias}'", "").replace(f'"{alias}"', "")
    assert "nova" not in text and "prefix" not in text
    assert _events(store) == before


def test_an_alias_this_project_holds_says_so(post: Any) -> None:
    """The project's own alias is a collision with itself, not with another."""
    response = post("PATCH", "", {"alias": "xo"})
    assert response.status_code == 409
    assert response.json()["message"] == "alias 'xo' is already used by this project"


def test_a_mixed_drop_says_nothing_about_mcp_tools(post: Any) -> None:
    """A drop of an item with children plus another field: neutral 422 text."""
    response = post(
        "PATCH",
        "/items/goal-1/batch-1",
        {"expected_version": 1, "state": "dropped", "title": "t"},
    )
    assert response.status_code == 422
    message = response.json()["message"]
    assert (
        "must be the only change; send the other changes in a separate update"
        in message
    )
    assert "item_update" not in message


def test_an_error_with_nothing_to_report_has_empty_details(post: Any) -> None:
    """details is always present: {} when the error carries no facts."""
    response = post("PATCH", "/items/goal-99", {"expected_version": 1, "title": "t"})
    assert response.status_code == 404
    assert response.json()["details"] == {}
