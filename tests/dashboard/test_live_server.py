"""
The real uvicorn server on an ephemeral port: the token is printed once to
stdout and appears in no log, whatever the requests carry.
"""

import logging
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2
import pytest
import uvicorn

from xoot.dashboard import runner

START_TIMEOUT_S = 10.0
CLIENT_LOGGERS = ("httpx2", "httpcore2")


@dataclass
class Live:
    """A running server: its port, the printed URL and its uvicorn instance."""

    port: int
    url: str
    server: uvicorn.Server


@pytest.fixture(name="live")
def fixture_live(
    store: Any,
    project: Any,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> Iterator[Live]:
    """serve() on a thread, stopped by setting should_exit after the test."""
    assert store and project
    servers: list[uvicorn.Server] = []

    class Recording(uvicorn.Server):
        """Records itself so the test can stop it."""

        def __init__(self, config: uvicorn.Config) -> None:
            super().__init__(config)
            servers.append(self)

    monkeypatch.setattr(uvicorn, "Server", Recording)
    sock = runner.bind(0)
    port = sock.getsockname()[1]
    thread = threading.Thread(target=runner.serve, args=(db_path, sock, False))
    thread.start()
    deadline = time.monotonic() + START_TIMEOUT_S
    while not (servers and servers[0].started):
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.02)
    url = capfd.readouterr().out.strip()
    try:
        yield Live(port, url, servers[0])
    finally:
        servers[0].should_exit = True
        thread.join(timeout=START_TIMEOUT_S)
        assert not thread.is_alive()


def test_the_token_is_printed_once_and_never_logged(
    live: Live, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    """Exchange, API reads and refusals: no log line holds the token."""
    caplog.set_level(logging.DEBUG)
    token = live.url.rsplit("token=", 1)[1]
    assert live.url == f"http://xoot.localhost:{live.port}/?token={token}"
    assert len(token) >= 43
    base = f"http://127.0.0.1:{live.port}"
    with httpx2.Client(
        base_url=base, headers={"host": f"127.0.0.1:{live.port}"}
    ) as client:
        exchange = client.get(f"/?token={token}", follow_redirects=False)
        assert exchange.status_code == 303
        client.cookies.set("xoot_token", token)
        assert client.get("/api/v1/projects").status_code == 200
        assert client.get(f"/api/v1/items/{token}").status_code == 404
        assert client.post(f"/?token={token}").status_code == 405
        assert client.get(f"/?token={token}x").status_code == 401
        bad_host = client.get(f"/?token={token}", headers={"host": "evil.example"})
        assert bad_host.status_code == 400
    captured = capfd.readouterr()
    # The test's own HTTP client logs its request URLs; the server must not.
    server_side = [
        record.getMessage()
        for record in caplog.records
        if not record.name.startswith(CLIENT_LOGGERS)
    ]
    assert not [line for line in server_side if token in line]
    assert token not in captured.err
    assert token not in captured.out


def test_uvicorn_runs_quiet(live: Live) -> None:
    """Access log off, warning level, no server header."""
    config = live.server.config
    assert config.access_log is False
    assert config.log_level == "warning"
    assert config.server_header is False
    assert logging.getLogger("uvicorn.access").level > logging.INFO or not (
        logging.getLogger("uvicorn.access").handlers
    )


def test_it_listens_on_loopback_only(live: Live) -> None:
    """The bound address is 127.0.0.1."""
    assert live.server.servers
    for server in live.server.servers:
        for sock in server.sockets:
            assert sock.getsockname()[0] == "127.0.0.1"
