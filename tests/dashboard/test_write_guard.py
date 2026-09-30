"""
The guard on every write route: the served Origin, the cookie and a JSON
body are all required; a query never authenticates a write; other methods
stay 405.
"""

import json
from http.cookies import SimpleCookie
from typing import Any

import pytest
from starlette.testclient import TestClient

from xoot.dashboard.guard import cookie_name

BASE = "/api/v1/projects/xoot"
JSON = {"content-type": "application/json"}

# Every write route, with a body it accepts on the seeded project.
WRITES: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", "/items", {"kind": "goal", "title": "new goal"}),
    ("PATCH", "/items/goal-1/batch-1/subtask-1", {"expected_version": 2, "title": "t"}),
    ("POST", "/moves", {"key": "goal-1/batch-1", "parent": "goal-1", "expected_version": 1}),
    ("POST", "/backlog", {"found_on": "goal-1", "title": "found", "body": "why"}),
    ("POST", "/backlog/covers", {"key": "goal-1/batch-1/backlog-1"}),
    ("POST", "/backlog/pushes", {"key": "goal-1/batch-1/backlog-1"}),
    ("POST", "/decisions", {"owner": "goal-1", "title": "decided"}),
    ("PATCH", "/decisions/goal-1/batch-1/decision-1", {"expected_version": 1, "title": "t"}),
    ("PATCH", "", {"name": "renamed"}),
]  # fmt: skip
IDS = [f"{method} {path or '/'}" for method, path, _ in WRITES]


def _send(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any],
    headers: dict[str, str],
    query: str = "",
) -> Any:
    return client.request(
        method, f"{BASE}{path}{query}", content=json.dumps(body), headers=headers
    )


def _refused(response: Any, status: int, error: str) -> None:
    assert response.status_code == status, response.text
    assert response.json() == {
        "error": error,
        "message": response.json()["message"],
        "details": {},
    }


@pytest.fixture(name="writes")
def fixture_writes(seeded: Any, launch: Any) -> dict[str, str]:
    """The seeded records every route names, and the served Origin."""
    assert seeded.decision_key == "goal-1/batch-1/decision-1"
    return {"origin": launch.origin, **JSON}


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_the_served_origin_cookie_and_json_pass(
    client: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """With everything in place the write reaches its route."""
    response = _send(client, method, path, body, writes)
    assert response.status_code in (200, 201), response.text


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_an_absent_origin_is_refused(
    client: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """Unlike a read, a write without an Origin header is a 403."""
    del writes["origin"]
    _refused(_send(client, method, path, body, writes), 403, "Forbidden")


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "http://localhost:{port}",
        "https://xoot.localhost:{port}",
        "http://xoot.localhost:{next_port}",
        "null",
    ],
)
@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_foreign_origin_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    writes: dict[str, str],
    launch: Any,
    method: str,
    path: str,
    body: dict[str, Any],
    origin: str,
) -> None:
    """Any Origin but the served one is a 403, other localhost ports included."""
    writes["origin"] = origin.format(port=launch.port, next_port=launch.port + 1)
    _refused(_send(client, method, path, body, writes), 403, "Forbidden")


@pytest.mark.parametrize(
    "content_type",
    [None, "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"],
)
@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_body_that_is_not_json_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
    content_type: str | None,
) -> None:
    """A missing or non-JSON Content-Type is a 415, the kind a form could send."""
    del writes["content-type"]
    if content_type is not None:
        writes["content-type"] = content_type
    _refused(_send(client, method, path, body, writes), 415, "UnsupportedMediaType")


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_json_with_a_charset_passes_the_guard(
    client: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """Media-type parameters do not matter."""
    writes["content-type"] = "application/json; charset=utf-8"
    assert _send(client, method, path, body, writes).status_code in (200, 201)


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_no_cookie_is_refused(
    anonymous: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """Served Origin and JSON, but no cookie: 401."""
    _refused(_send(anonymous, method, path, body, writes), 401, "Unauthorized")


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_wrong_cookie_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    anonymous: TestClient,
    writes: dict[str, str],
    launch: Any,
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """A cookie that is not the token: 401."""
    anonymous.cookies.set(cookie_name(launch.port), launch.token + "x")
    _refused(_send(anonymous, method, path, body, writes), 401, "Unauthorized")


@pytest.mark.parametrize("name", ["token", "launch"])
@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_query_never_authenticates_a_write(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    anonymous: TestClient,
    writes: dict[str, str],
    launch: Any,
    method: str,
    path: str,
    body: dict[str, Any],
    name: str,
) -> None:
    """The valid token in the URL, no cookie: 401, no cookie set, nothing written."""
    query = f"?{name}={launch.token}"
    response = _send(anonymous, method, path, body, writes, query)
    _refused(response, 401, "Unauthorized")
    assert "set-cookie" not in response.headers
    assert SimpleCookie(response.headers.get("set-cookie", "")) == SimpleCookie()


@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_query_on_an_authenticated_write_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    writes: dict[str, str],
    launch: Any,
    method: str,
    path: str,
    body: dict[str, Any],
) -> None:
    """With the cookie, a stray query is invalid input, not a login."""
    response = _send(client, method, path, body, writes, f"?token={launch.token}")
    assert response.status_code == 422
    assert response.json()["error"] == "ValidationError"


@pytest.mark.parametrize(
    "host", ["evil.example:{port}", "xoot.localhost:{next_port}", "0.0.0.0:{port}"]
)
@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_a_bad_host_is_refused(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    writes: dict[str, str],
    launch: Any,
    method: str,
    path: str,
    body: dict[str, Any],
    host: str,
) -> None:
    """DNS rebinding: a Host outside the allowlist is a 400 before anything else."""
    writes["host"] = host.format(port=launch.port, next_port=launch.port + 1)
    response = _send(client, method, path, body, writes)
    assert response.status_code == 400
    assert response.json()["error"] == "BadRequest"


@pytest.mark.parametrize("other", ["PUT", "DELETE", "OPTIONS"])
@pytest.mark.parametrize(("method", "path", "body"), WRITES, ids=IDS)
def test_other_methods_on_write_routes_are_405(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: TestClient,
    writes: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any],
    other: str,
) -> None:
    """PUT, DELETE and OPTIONS stay 405; Allow names the route's write method."""
    response = _send(client, other, path, body, writes)
    assert response.status_code == 405
    assert response.json()["error"] == "MethodNotAllowed"
    assert response.headers["allow"].split(", ")[:2] == ["GET", "HEAD"]
    assert method in response.headers["allow"]


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "path", ["/", "/xoot/tree", "/assets/app.js", "/api/v1/projects", "/api/v1/meta"]
)
def test_writes_elsewhere_stay_405(
    client: TestClient, writes: dict[str, str], method: str, path: str
) -> None:
    """Outside the write routes, even a complete write request is a 405."""
    response = client.request(method, path, content="{}", headers=writes)
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, HEAD"


def test_the_wrong_write_method_on_a_route_is_405(
    client: TestClient, writes: dict[str, str]
) -> None:
    """PATCH on a POST-only route, and the reverse, are 405."""
    assert _send(client, "PATCH", "/items", {}, writes).status_code == 405
    assert _send(client, "POST", "/items/goal-1", {}, writes).status_code == 405


def test_write_refusals_carry_the_security_headers(
    anonymous: TestClient, writes: dict[str, str]
) -> None:
    """A refused write still gets the CSP, nosniff and no-store."""
    response = _send(
        anonymous, "POST", "/items", {"kind": "goal", "title": "g"}, writes
    )
    assert response.status_code == 401
    assert "content-security-policy" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
