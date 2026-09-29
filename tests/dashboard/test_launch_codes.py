"""--open's one-time launch codes, and the cookie named after the port."""

from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from xoot.dashboard.app import create_app
from xoot.dashboard.guard import cookie_name
from xoot.dashboard.launch_codes import LAUNCH_TTL_S, LaunchCodes
from xoot.dashboard.runner import launch_url

API = "/api/v1/projects"


def test_a_code_is_single_use() -> None:
    """The first redeem succeeds; a second one, or a guess, does not."""
    codes = LaunchCodes()
    code = codes.issue()
    assert codes.redeem(code) is True
    assert codes.redeem(code) is False
    assert codes.redeem("guess") is False
    assert codes.redeem("t\xf6k") is False


def test_a_code_expires_after_30_seconds() -> None:
    """Past the TTL the code fails and is spent anyway."""
    now = [0.0]
    codes = LaunchCodes(lambda: now[0])
    code = codes.issue()
    assert LAUNCH_TTL_S == 30.0
    now[0] = LAUNCH_TTL_S
    assert codes.redeem(code) is False
    now[0] = 0.0
    assert codes.redeem(code) is False
    fresh = codes.issue()
    now[0] = LAUNCH_TTL_S - 0.1
    assert codes.redeem(fresh) is True


def test_launch_url_carries_the_code_never_the_token() -> None:
    """The opener's URL has only ?launch=<code>."""
    assert launch_url(7373, "abc") == "http://xoot.localhost:7373/?launch=abc"


def test_redeeming_sets_the_token_cookie_once(
    store: Any, db_path: Path, static_dir: Path, launch: Any
) -> None:
    """A valid code sets the token cookie; the same code again is a 401."""
    assert store.path == db_path
    codes = LaunchCodes()
    code = codes.issue()
    app = create_app(db_path, launch.token, launch.port, static_dir, codes)
    with TestClient(app, base_url=launch.origin, follow_redirects=False) as client:
        response = client.get(f"/?launch={code}")
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        cookie = SimpleCookie(response.headers["set-cookie"])[cookie_name(launch.port)]
        assert cookie.value == launch.token
        assert client.get(API).status_code == 200
        client.cookies.clear()
        replay = client.get(f"/?launch={code}")
        assert replay.status_code == 401
        assert "set-cookie" not in replay.headers
        assert client.get(f"/?launch={codes.issue()}&launch=x").status_code == 401


def test_without_codes_a_launch_query_is_refused(anonymous: TestClient) -> None:
    """An app built without codes accepts none."""
    assert anonymous.get("/?launch=anything").status_code == 401


def test_cookie_name_includes_the_port(
    store: Any, db_path: Path, static_dir: Path, launch: Any
) -> None:
    """Two dashboards on two ports never read each other's cookie."""
    assert store.path == db_path
    assert cookie_name(7373) == "xoot_token_7373"
    other_port = launch.port + 1
    app = create_app(db_path, launch.token, other_port, static_dir)
    base = f"http://xoot.localhost:{other_port}"
    with TestClient(app, base_url=base, follow_redirects=False) as client:
        client.cookies.set(cookie_name(launch.port), launch.token)
        assert client.get(API).status_code == 401
        client.cookies.set(cookie_name(other_port), launch.token)
        assert client.get(API).status_code == 200
