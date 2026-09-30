"""The guard: Host allowlist, methods and write routes, cookie, Origin, headers."""

from http.cookies import SimpleCookie
from typing import Any

import anyio
import pytest
from starlette.testclient import TestClient

from xoot.dashboard.guard import cookie_name, guard
from xoot.dashboard.headers import CSP

API = "/api/v1/projects"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", [API, "/", "/assets/app.js"])
def test_only_get_and_head_are_allowed(
    client: TestClient, method: str, path: str
) -> None:
    """Any other method is a 405 naming the allowed ones."""
    response = client.request(method, path)
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, HEAD"
    assert response.json()["error"] == "MethodNotAllowed"


def test_api_needs_the_cookie(anonymous: TestClient) -> None:
    """No cookie: 401."""
    response = anonymous.get(API)
    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


@pytest.mark.parametrize("case", ["other", "suffixed", "truncated", "empty"])
def test_api_refuses_a_wrong_cookie(
    launch: Any, anonymous: TestClient, case: str
) -> None:
    """A cookie that is not the launch token: 401."""
    cookie = {
        "other": "wrong",
        "suffixed": launch.token + "x",
        "truncated": launch.token[:-1],
        "empty": "",
    }[case]
    anonymous.headers["cookie"] = f"{cookie_name(launch.port)}={cookie}"
    assert anonymous.get(API).status_code == 401


def test_page_and_assets_need_no_token(anonymous: TestClient) -> None:
    """index.html and the static assets hold no data."""
    assert anonymous.get("/").status_code == 200
    assert anonymous.get("/xoot/item/goal-1").status_code == 200
    assert anonymous.get("/assets/app.js").status_code == 200


@pytest.mark.parametrize("path", ["/", "/xoot/item/goal-3", API])
def test_token_exchange_sets_the_cookie_and_drops_the_query(
    launch: Any, anonymous: TestClient, path: str
) -> None:
    """A valid ?token sets xoot_token_<port> with every flag and redirects without it."""
    response = anonymous.get(f"{path}?token={launch.token}&other=1")
    assert response.status_code == 303
    assert response.headers["location"] == path
    assert response.headers["cache-control"] == "no-store"
    cookie = SimpleCookie(response.headers["set-cookie"])[cookie_name(launch.port)]
    assert cookie.value == launch.token
    assert cookie["httponly"] is True
    assert cookie["samesite"].lower() == "strict"
    assert cookie["path"] == "/"
    assert not cookie["secure"]
    assert anonymous.get(API).status_code == 200


def test_a_wrong_token_query_is_refused(launch: Any, anonymous: TestClient) -> None:
    """A wrong or repeated ?token sets no cookie."""
    for query in ("token=nope", f"token={launch.token}&token={launch.token}"):
        response = anonymous.get(f"/?{query}")
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
    assert anonymous.get(API).status_code == 401


@pytest.mark.parametrize("path", ["//evil.example/x", "/a\\b"])
def test_the_redirect_never_leaves_the_origin(
    launch: Any, anonymous: TestClient, path: str
) -> None:
    """A path that a browser would read as another host redirects to /."""
    response = anonymous.get(
        f"http://xoot.localhost:{launch.port}{path}?token={launch.token}"
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:{port}",
        "xoot.localhost",
        "xoot.localhost:{next_port}",
        "localhost.evil.example:{port}",
        "0.0.0.0:{port}",
        "",
    ],
)
def test_a_host_outside_the_allowlist_is_refused(
    launch: Any, client: TestClient, host: str
) -> None:
    """Every host but the three names on the served port: 400, even the page."""
    value = host.format(port=launch.port, next_port=launch.port + 1)
    for path in (API, "/"):
        response = client.get(path, headers={"host": value})
        assert response.status_code == 400
        assert response.json()["error"] == "BadRequest"


@pytest.mark.parametrize("name", ["xoot.localhost", "localhost", "127.0.0.1"])
def test_each_allowed_host_is_served(
    launch: Any, client: TestClient, name: str
) -> None:
    """The three names on the served port are served."""
    response = client.get(API, headers={"host": f"{name}:{launch.port}"})
    assert response.status_code == 200


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
def test_a_foreign_origin_is_refused_on_the_api(
    client: TestClient, origin: str
) -> None:
    """With the cookie, an Origin other than the served one: 403."""
    response = client.get(API, headers={"origin": origin})
    assert response.status_code == 403
    assert response.json()["error"] == "Forbidden"


def test_the_served_origin_and_no_origin_pass(launch: Any, client: TestClient) -> None:
    """Same-origin fetches, with or without an Origin header, are served."""
    assert client.get(API, headers={"origin": launch.origin}).status_code == 200
    assert client.get(API).status_code == 200


def _responses(launch: Any, anonymous: TestClient) -> dict[str, object]:
    """One response of each kind the dashboard sends."""
    kinds = {
        "page": anonymous.get("/"),
        "asset": anonymous.get("/assets/app.js"),
        "missing_asset": anonymous.get("/assets/nope.js"),
        "redirect": anonymous.get(f"/?token={launch.token}"),
        "bad_host": anonymous.get("/", headers={"host": "evil.example"}),
        "method": anonymous.post("/"),
        "bad_token": anonymous.get("/?token=x"),
    }
    kinds["api"] = anonymous.get(API)
    kinds["api_404"] = anonymous.get("/api/v1/projects/xoot/items/goal-99")
    kinds["api_400"] = anonymous.get("/api/v1/projects?x=1")
    kinds["api_403"] = anonymous.get(API, headers={"origin": "http://evil.example"})
    anonymous.cookies.clear()
    kinds["api_401"] = anonymous.get(API)
    return kinds


def test_security_headers_are_on_every_response(
    launch: Any, anonymous: TestClient
) -> None:
    """CSP, nosniff and no-referrer everywhere; no-store on every /api reply."""
    for kind, response in _responses(launch, anonymous).items():
        headers = response.headers  # type: ignore[attr-defined]
        assert headers["content-security-policy"] == CSP, kind
        assert headers["x-content-type-options"] == "nosniff", kind
        assert headers["referrer-policy"] == "no-referrer", kind
        if kind.startswith("api"):
            assert headers["cache-control"] == "no-store", kind


def test_the_csp_is_the_locked_policy() -> None:
    """No unsafe-inline, no unsafe-eval, nothing but self for scripts."""
    assert CSP == (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )


def test_non_ascii_cookie_bytes_are_refused(launch: Any) -> None:
    """Raw non-ASCII cookie bytes reach the comparison as text and fail it."""
    app = guard(_unreachable, token=launch.token, port=launch.port)
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": API,
        "query_string": b"",
        "headers": [
            (b"host", f"xoot.localhost:{launch.port}".encode()),
            (b"cookie", f"{cookie_name(launch.port)}=t\xf6k".encode("latin-1")),
        ],
    }
    anyio.run(app, scope, receive, send)
    assert sent[0]["status"] == 401


async def _unreachable(scope: Any, receive: Any, send: Any) -> None:
    raise AssertionError("the guard let the request through")
