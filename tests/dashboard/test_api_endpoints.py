"""Every /api/v1 endpoint on a seeded tmp database."""

from typing import Any

import pytest
from starlette.testclient import TestClient

from xoot import __version__
from xoot.models.event.actor import Actor
from xoot.models.fields import format_timestamp
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_close import SessionClose
from xoot.server.brief import LIST_MAX
from xoot.services.session_close_service import close_session
from xoot.store.store import Store


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
    """No header, resolved_by or db_path; the open-session backlog is there."""
    brief = _ok(client, "/api/v1/projects/xoot/brief")
    assert not {"header", "resolved_by", "db_path"} & set(brief)
    assert brief["project"]["key_prefix"] == "xoot"
    assert [i["key"] for i in brief["open_session_backlog"]] == [seeded.held.key]
    assert brief["open_session_backlog_truncated"] is False
    assert len(brief["open_sessions"]) <= LIST_MAX


def test_tree_defaults_and_parameters(client: TestClient, seeded: Any) -> None:
    """Done items are hidden by default and shown with include_done."""
    default = _ok(client, "/api/v1/projects/xoot/tree")
    keys = [n["item"]["key"] for n in default["nodes"]]
    assert seeded.subtask.key not in keys
    assert default["project"] == "xoot"
    full = _ok(
        client, "/api/v1/projects/xoot/tree?include_done=true&depth=8&limit=1000"
    )
    assert seeded.subtask.key in [n["item"]["key"] for n in full["nodes"]]
    rooted = _ok(client, f"/api/v1/projects/xoot/tree?root={seeded.batch.key}&depth=0")
    assert [n["item"]["key"] for n in rooted["nodes"]] == [seeded.batch.key]
    capped = _ok(client, "/api/v1/projects/xoot/tree?limit=1")
    assert capped["truncated"] is True


@pytest.mark.parametrize(
    "query", ["depth=9", "limit=0", "depth=x", "include_done=maybe", "extra=1"]
)
def test_tree_refuses_bad_parameters(
    client: TestClient, seeded: Any, query: str
) -> None:
    """Out-of-range, mistyped and unknown parameters are a 400 ValidationError."""
    assert seeded
    response = client.get(f"/api/v1/projects/xoot/tree?{query}")
    assert response.status_code == 400
    assert response.json()["error"] == "ValidationError"


def test_tree_root_must_exist(client: TestClient, seeded: Any) -> None:
    """An unknown root key is a 404 naming the key."""
    assert seeded
    response = client.get("/api/v1/projects/xoot/tree?root=xoot-99")
    assert response.status_code == 404
    assert response.json() == {
        "error": "NotFoundError",
        "message": "not found: xoot-99",
    }


def test_sessions_list_and_filter(client: TestClient, seeded: Any) -> None:
    """Every session is listed; status filters; a bad status is a 400."""
    listed = _ok(client, "/api/v1/projects/xoot/sessions")
    assert [s["key"] for s in listed["sessions"]] == ["xoot-S1"]
    assert seeded.session.id
    assert not _ok(client, "/api/v1/projects/xoot/sessions?status=closed")["sessions"]
    assert client.get("/api/v1/projects/xoot/sessions?status=gone").status_code == 400


def test_session_detail_lists_linked_items(client: TestClient, seeded: Any) -> None:
    """The overlay's item keys: the focus goal and the capture."""
    view = _ok(client, "/api/v1/projects/xoot/sessions/xoot-S1")
    assert view["session"]["status"] == "open"
    assert view["summary"] is None
    assert view["items"] == [seeded.goal.key, seeded.held.key]
    assert [
        (e["item"]["key"], e["item"]["kind"], e["disposition"], e["captured"])
        for e in view["linked"]
    ] == [
        (seeded.goal.key, "goal", None, False),
        (seeded.held.key, "subtask", None, True),
    ]
    assert view["linked"][1]["item"]["state"] == "backlogged"


def test_sessions_list_counts_linked_items(client: TestClient, seeded: Any) -> None:
    """The table's count: the focus goal and the capture."""
    assert seeded
    [row] = _ok(client, "/api/v1/projects/xoot/sessions")["sessions"]
    assert row["linked_items"] == 2
    assert {"key", "title", "client", "status", "started_at", "closed_at"} <= set(row)


def test_closed_session_detail_reports_dispositions(
    client: TestClient, seeded: Any, store: Store, user: Actor
) -> None:
    """After the close, each open linked item shows the disposition it got."""
    close_session(
        store,
        seeded.session.id,
        SessionClose(
            dispositions={
                seeded.goal.id: Disposition.CARRY_OVER,
                seeded.held.id: Disposition.PROJECT_BACKLOG,
            }
        ),
        user,
    )
    view = _ok(client, "/api/v1/projects/xoot/sessions/xoot-S1")
    assert view["session"]["status"] == "closed"
    assert [(e["item"]["key"], e["disposition"]) for e in view["linked"]] == [
        (seeded.goal.key, "carry_over"),
        (seeded.held.key, "project_backlog"),
    ]


def test_session_of_another_project_is_not_found(
    client: TestClient, seeded: Any, other_project: object
) -> None:
    """A session key is only found under its own project's prefix."""
    assert seeded and other_project
    response = client.get("/api/v1/projects/nova/sessions/xoot-S1")
    assert response.status_code == 404


def test_backlogs_per_open_session_project_and_unfiled(
    client: TestClient, seeded: Any
) -> None:
    """The capture shows under its session and under unfiled."""
    view = _ok(client, "/api/v1/projects/xoot/backlogs")
    assert [e["session"]["key"] for e in view["sessions"]] == ["xoot-S1"]
    assert [i["key"] for i in view["sessions"][0]["items"]] == [seeded.held.key]
    assert not view["project_backlog"]
    assert seeded.held.key in [i["key"] for i in view["unfiled"]]
    assert view["project_backlog_truncated"] is False
    [row] = view["sessions"][0]["items"]
    assert row["created_at"] == format_timestamp(seeded.held.created_at)


def test_decisions_list(client: TestClient, seeded: Any) -> None:
    """Summaries only, newest first, with the scope key."""
    view = _ok(client, "/api/v1/projects/xoot/decisions")
    assert [(d["key"], d["scope"]) for d in view["decisions"]] == [
        (seeded.decision_key, seeded.goal.key)
    ]
    assert "body" not in view["decisions"][0]


def test_changes_moves_after_a_write(
    client: TestClient, seeded: Any, make_item: Any, project: Any
) -> None:
    """latest_event_id grows when the project is written."""
    assert seeded
    before = _ok(client, "/api/v1/projects/xoot/changes")["latest_event_id"]
    make_item(project, "goal")
    after = _ok(client, "/api/v1/projects/xoot/changes")["latest_event_id"]
    assert after > before > 0


def test_item_detail(client: TestClient, seeded: Any) -> None:
    """Body, children, events, sessions and scoped decisions with bodies."""
    view = _ok(client, f"/api/v1/items/{seeded.goal.key}")
    assert view["item"]["body"] == "<b>body</b>"
    assert [c["key"] for c in view["children"]["items"]] == [seeded.batch.key]
    assert view["events"][0]["action"] == "create"
    assert [s["key"] for s in view["sessions"]] == ["xoot-S1"]
    assert [d["body"] for d in view["decisions"]] == ["decision body"]


def test_decision_detail_has_the_body(client: TestClient, seeded: Any) -> None:
    """GET /decisions/{key} carries the body."""
    view = _ok(client, f"/api/v1/decisions/{seeded.decision_key}")
    assert view["decision"]["body"] == "decision body"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/v1/projects/nope/brief", "not found: nope"),
        ("/api/v1/items/xoot-99", "not found: xoot-99"),
        ("/api/v1/items/%3Cscript%3E", "not found: malformed key"),
        ("/api/v1/decisions/xoot-D99", "not found: xoot-D99"),
        ("/api/v1/nothing", "no such endpoint"),
        ("/api", "no such endpoint"),
        ("/api/v2/projects", "no such endpoint"),
    ],
)
def test_unknown_records_and_paths_are_json_404(
    client: TestClient, seeded: Any, path: str, message: str
) -> None:
    """A 404 body never echoes malformed input."""
    assert seeded
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"error": "NotFoundError", "message": message}


def test_head_is_allowed(client: TestClient, seeded: Any) -> None:
    """HEAD answers like GET, without a body."""
    assert seeded
    response = client.head("/api/v1/projects/xoot/brief")
    assert response.status_code == 200
    assert not response.content


def test_other_paths_serve_the_page(client: TestClient) -> None:
    """Client-side routes get index.html; assets are served from the bundle."""
    for path in ("/", "/xoot", "/xoot/focus/xoot-1", "/xoot/item/xoot-2"):
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
