"""`xoot dashboard`: the port-in-use exit, the URL printed once, Ctrl+C, --open."""

import re
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from xoot.cli import exit_codes
from xoot.dashboard import runner

URL = re.compile(r"^http://xoot\.localhost:(\d+)/\?token=([A-Za-z0-9_-]{43,})$")


@pytest.fixture(name="served")
def fixture_served(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    """Replace uvicorn's run loop; record each config and socket it gets."""
    calls: list[Any] = []

    def run(self: uvicorn.Server, sockets: list[socket.socket]) -> None:
        calls.append((self.config, sockets))

    monkeypatch.setattr(uvicorn.Server, "run", run)
    yield calls


@pytest.fixture(name="busy_port")
def fixture_busy_port() -> Iterator[int]:
    """A port some other socket already listens on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield sock.getsockname()[1]


def test_prints_the_url_once_and_serves_on_loopback(
    xoot: Any, served: list[Any], db_path: Path
) -> None:
    """One stdout line, the token URL; the socket is 127.0.0.1 on --port."""
    result = xoot("dashboard", "--port", _free_port())
    assert result.code == exit_codes.OK
    lines = result.out.splitlines()
    assert len(lines) == 1
    match = URL.fullmatch(lines[0])
    assert match is not None
    token = match.group(2)
    assert result.out.count(token) == 1
    assert token not in result.err
    ((config, sockets),) = served
    assert sockets[0].fileno() == -1  # closed once serving ended
    assert config.access_log is False
    assert config.log_level == "warning"
    assert db_path.exists()


def test_each_launch_has_a_new_token(xoot: Any, served: list[Any]) -> None:
    """Two launches, two tokens."""
    first = URL.fullmatch(xoot("dashboard", "--port", _free_port()).out.strip())
    second = URL.fullmatch(xoot("dashboard", "--port", _free_port()).out.strip())
    assert first and second and served
    assert first.group(2) != second.group(2)


def test_a_port_in_use_exits_3(xoot: Any, served: list[Any], busy_port: int) -> None:
    """Nothing is served or printed to stdout; stderr says why."""
    result = xoot("dashboard", "--port", str(busy_port))
    assert result.code == exit_codes.UNAVAILABLE == 3
    assert not result.out
    assert f"port {busy_port} is in use" in result.err
    assert "--port" in result.err
    assert not served


def test_the_default_port_is_7373(served: list[Any]) -> None:
    """The parser default and the runner default agree."""
    assert served == []
    assert runner.DEFAULT_PORT == 7373


@pytest.mark.parametrize("port", ["0", "0x", "-1", "65536", "abc"])
def test_a_bad_port_is_a_usage_error(xoot: Any, port: str) -> None:
    """Out-of-range or non-numeric --port exits 2."""
    assert xoot("dashboard", "--port", port).code == exit_codes.USAGE


def test_ctrl_c_stops_cleanly(xoot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uvicorn re-raising SIGINT after shutdown still exits 0."""

    def interrupted(_self: uvicorn.Server, sockets: list[socket.socket]) -> None:
        assert sockets
        raise KeyboardInterrupt

    monkeypatch.setattr(uvicorn.Server, "run", interrupted)
    result = xoot("dashboard", "--port", _free_port())
    assert result.code == exit_codes.OK
    assert URL.fullmatch(result.out.strip())


def test_open_hands_the_url_to_the_opener(
    xoot: Any, served: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    --open hands the opener a one-time launch code, never the printed token;
    a failure warns and keeps serving.
    """
    opened: list[str] = []

    def fail(url: str) -> bool:
        opened.append(url)
        return False

    monkeypatch.setattr(runner, "open_url", fail)
    result = xoot("dashboard", "--port", _free_port(), "--open")
    assert result.code == exit_codes.OK
    assert len(opened) == 1
    url = opened[0]
    printed = result.out.strip()
    assert url.startswith(printed.split("?")[0] + "?launch=")
    assert printed.split("token=")[1] not in url
    assert "warning: could not open a browser" in result.err
    assert len(served) == 1


def test_without_open_no_browser_is_touched(
    xoot: Any, served: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """No --open, no opener call."""

    def forbidden(url: str) -> bool:
        raise AssertionError(url)

    monkeypatch.setattr(runner, "open_url", forbidden)
    assert xoot("dashboard", "--port", _free_port()).code == exit_codes.OK
    assert served


def _free_port() -> str:
    """A port nothing listens on right now (the kernel's pick, released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])
