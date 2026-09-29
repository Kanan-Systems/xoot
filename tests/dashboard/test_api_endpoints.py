"""Every /api/v1 endpoint on a seeded tmp database, nested keys included."""

from typing import Any

import pytest
from starlette.testclient import TestClient

from xoot import __version__
from xoot.dashboard.views.project_views import first_line
from xoot.models.fields import format_timestamp

BASE = "/api/v1/projects/xoot"


def _ok(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    return response.json()


def test_meta_reports_the_version(client: TestClient) -> None:
    """GET /meta is the running version."""
    assert _ok(client, "/api/v1/meta") == {"version": __version__}


def test_projects_list_prefix_name_and_aliases_only(
    client: TestClient, seeded: Any
) -> None:
    """Paths are not sent to the browser."""
    assert seeded
    assert _ok(client, "/api/v1/projects") == {
        "projects": [{"key_prefix": "xoot", "name": "xoot", "aliases": ["xo"]}]
    }


def test_brief_drops_the_mcp_only_fields(client: TestClient, seeded: Any) -> None:
    """No header, resolved_by or db_path; goals, blocks and backlog are there."""
    brief = _ok(client, f"{BASE}/brief")
    assert not {"header", "resolved_by", "db_path"} & set(brief)
    assert brief["project"]["key_prefix"] == "xoot"
    assert [g["key"] for g in brief["open_goals"]] == [seeded.goal.key]
    assert brief["blocked"] == [{"key": seeded.batch.key, "open_backlog": 1}]
    assert brief["backlog_counts"] == {"project": 0, "goal": 0, "batch": 1}
    assert "open_sessions" not in brief


def test_tree_defaults_and_parameters(client: TestClient, seeded: Any) -> None:
    """Done items are hidden by default and shown with include_done."""
    default = _ok(client, f"{BASE}/tree")
    keys = [n["item"]["key"] for n in default["nodes"]]
    assert seeded.subtask.key not in keys and seeded.held.key in keys
    assert default["project"] == "xoot"
    full = _ok(client, f"{BASE}/tree?include_done=true&depth=8&limit=1000")
    assert seeded.subtask.key in [n["item"]["key"] for n in full["nodes"]]
    one_goal = _ok(client, f"{BASE}/tree?goal={seeded.goal.key}&depth=0")
    assert [n["item"]["key"] for n in one_goal["nodes"]] == [seeded.goal.key]
    capped = _ok(client, f"{BASE}/tree?limit=1")
    assert capped["truncated"] is True


@pytest.mark.parametrize(
    "query", ["depth=9", "limit=0", "depth=x", "include_done=maybe", "root=goal-1"]
)
def test_tree_refuses_bad_parameters(
    client: TestClient, seeded: Any, query: str
) -> None:
    """Out-of-range, mistyped and unknown parameters are a 400 ValidationError."""
    assert seeded
    response = client.get(f"{BASE}/tree?{query}")
    assert response.status_code == 400
    assert response.json()["error"] == "ValidationError"


def test_tree_goal_must_exist(client: TestClient, seeded: Any) -> None:
    """An unknown goal key is a 404 naming the key."""
    assert seeded
    response = client.get(f"{BASE}/tree?goal=goal-99")
    assert response.status_code == 404
    assert response.json() == {
        "error": "NotFoundError",
        "message": "not found: goal-99",
    }


def test_backlog_lists_every_level(client: TestClient, seeded: Any) -> None:
    """Open backlog with its level, the item it was found on and its creation."""
    view = _ok(client, f"{BASE}/backlog")
    [row] = view["items"]
    assert (row["key"], row["level"], row["found_on"]) == (
        seeded.held.key,
        "batch",
        seeded.subtask.key,
    )
    assert row["created_at"] == format_timestamp(seeded.held.created_at)
    assert row["why"] == "why"
    assert view["truncated"] is False


@pytest.mark.parametrize(
    ("body", "why"),
    [("", ""), ("\n  \nsecond\nthird", "second"), ("x" * 300, "x" * 200)],
)
def test_why_is_the_first_nonblank_line(body: str, why: str) -> None:
    """Blank bodies stay empty; long lines are cut."""
    assert first_line(body) == why


def test_tree_lists_what_backlog_blocks(client: TestClient, seeded: Any) -> None:
    """Every blocked goal and batch, whatever the tree's own bounds."""
    view = _ok(client, f"{BASE}/tree?depth=0")
    assert view["blocked"] == [{"key": seeded.batch.key, "open_backlog": 1}]


def test_decisions_list(client: TestClient, seeded: Any) -> None:
    """Summaries only, newest first, with the owner key."""
    view = _ok(client, f"{BASE}/decisions")
    assert [(d["key"], d["owner"]) for d in view["decisions"]] == [
        (seeded.decision_key, seeded.batch.key)
    ]
    assert "body" not in view["decisions"][0]


def test_changes_moves_after_a_write(
    client: TestClient, seeded: Any, make_item: Any, project: Any
) -> None:
    """latest_event_id grows when the project is written."""
    assert seeded
    before = _ok(client, f"{BASE}/changes")["latest_event_id"]
    make_item(project, "goal")
    after = _ok(client, f"{BASE}/changes")["latest_event_id"]
    assert after > before > 0


def test_item_detail_with_a_nested_key(client: TestClient, seeded: Any) -> None:
    """Keys with "/" reach the route whole: body, children, events, decisions."""
    view = _ok(client, f"{BASE}/items/{seeded.batch.key}")
    assert view["item"]["key"] == "goal-1/batch-1"
    assert [c["key"] for c in view["children"]["items"]] == [
        seeded.subtask.key,
        seeded.held.key,
    ]
    assert view["events"][0]["action"] == "create"
    assert [d["body"] for d in view["decisions"]] == ["decision body"]
    deep = _ok(client, f"{BASE}/items/{seeded.held.key}")
    assert deep["item"]["found_on"] == seeded.subtask.key
    goal = _ok(client, f"{BASE}/items/{seeded.goal.key}")
    assert goal["item"]["body"] == "<b>body</b>"


def test_decision_detail_has_the_body(client: TestClient, seeded: Any) -> None:
    """GET /decisions/{key} carries the body; the key holds slashes."""
    view = _ok(client, f"{BASE}/decisions/{seeded.decision_key}")
    assert seeded.decision_key == "goal-1/batch-1/decision-1"
    assert view["decision"]["body"] == "decision body"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/v1/projects/nope/brief", "not found: nope"),
        (f"{BASE}/items/goal-99", "not found: goal-99"),
        (
            f"{BASE}/items/goal-1/batch-9/subtask-1",
            "not found: goal-1/batch-9/subtask-1",
        ),
        (f"{BASE}/items/%3Cscript%3E", "not found: malformed key"),
        (f"{BASE}/items/xoot-1", "not found: malformed key"),
        (f"{BASE}/decisions/goal-1/decision-99", "not found: goal-1/decision-99"),
        ("/api/v1/projects/nova/items/goal-1", "not found: goal-1"),
        (f"{BASE}/sessions", "no such endpoint"),
        ("/api/v1/items/goal-1", "no such endpoint"),
        ("/api/v1/nothing", "no such endpoint"),
        ("/api", "no such endpoint"),
        ("/api/v2/projects", "no such endpoint"),
    ],
)
@pytest.mark.usefixtures("other_project")
def test_unknown_records_and_paths_are_json_404(
    client: TestClient, seeded: Any, path: str, message: str
) -> None:
    """A 404 body never echoes malformed input; sessions routes are gone."""
    assert seeded
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"error": "NotFoundError", "message": message}


def test_head_is_allowed(client: TestClient, seeded: Any) -> None:
    """HEAD answers like GET, without a body."""
    assert seeded
    response = client.head(f"{BASE}/brief")
    assert response.status_code == 200
    assert not response.content


def test_other_paths_serve_the_page(client: TestClient) -> None:
    """Client-side routes get index.html; assets are served from the bundle."""
    for path in ("/", "/xoot", "/xoot/item/goal-1/batch-2"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<title>xoot</title>" in response.text
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert client.get("/assets/missing.js").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/assets/..%2f..%2fconftest.py",
        "/assets/%2e%2e/%2e%2e/conftest.py",
        "/assets/..%5c..%5cconftest.py",
        "/assets/..%2findex.html",
    ],
)
def test_assets_cannot_escape_the_bundle(client: TestClient, path: str) -> None:
    """Encoded traversal out of /assets/ is a 404, never a file's content."""
    response = client.get(path)
    assert response.status_code == 404
    assert "fixture" not in response.text
