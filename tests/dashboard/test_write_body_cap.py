"""
Write bodies are capped at MAX_BODY_BYTES on the bytes received, after the
guard: a lying Content-Length or a chunked body cannot get past the cap,
and a request the guard refuses never has its body read.
"""

import json
from pathlib import Path
from typing import Any

import anyio
import pytest
from starlette.testclient import TestClient

from xoot.dashboard.app import create_app
from xoot.dashboard.guard import cookie_name
from xoot.dashboard.write_api import MAX_BODY_BYTES
from xoot.store.store import Store

PATH = "/api/v1/projects/xoot/items"
CHUNK = 4096


def _exactly(size: int) -> bytes:
    """A JSON object of exactly size bytes whose title is far too long."""
    frame = json.dumps({"kind": "goal", "title": ""}).encode()
    body = json.dumps({"kind": "goal", "title": "x" * (size - len(frame))}).encode()
    assert len(body) == size
    return body


def _headers(
    launch: Any, cookie: bool = True, **extra: str
) -> list[tuple[bytes, bytes]]:
    headers = {
        "host": f"xoot.localhost:{launch.port}",
        "origin": launch.origin,
        "content-type": "application/json",
        **extra,
    }
    if cookie:
        headers["cookie"] = f"{cookie_name(launch.port)}={launch.token}"
    return [(k.encode(), v.encode()) for k, v in headers.items()]


def _drive(
    app: Any, headers: list[tuple[bytes, bytes]], chunks: list[bytes]
) -> tuple[int, dict[str, Any], int]:
    """Send one POST through the ASGI app; return status, body and chunks read."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": PATH,
        "raw_path": PATH.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 7373),
    }
    pending = list(chunks)
    read = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal read
        if not pending:
            return {"type": "http.request", "body": b"", "more_body": False}
        read += 1
        chunk = pending.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(pending)}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    anyio.run(app, scope, receive, send)
    status = sent[0]["status"]
    body = b"".join(m.get("body", b"") for m in sent[1:])
    return status, json.loads(body), read


def _split(data: bytes) -> list[bytes]:
    return [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]


@pytest.fixture(name="app")
def fixture_app(store: Store, db_path: Path, static_dir: Path, launch: Any) -> Any:
    """The dashboard app on the test database, the project registered."""
    assert store.path == db_path
    return create_app(db_path, launch.token, launch.port, static_dir)


@pytest.mark.usefixtures("project")
def test_exactly_the_cap_reaches_validation(client: TestClient, launch: Any) -> None:
    """65536 bytes are read and validated: the title is refused, not the size."""
    assert MAX_BODY_BYTES == 65536
    response = client.post(
        PATH,
        content=_exactly(MAX_BODY_BYTES),
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "ValidationError"


@pytest.mark.usefixtures("project")
def test_one_byte_over_is_413(client: TestClient, launch: Any) -> None:
    """65537 bytes: 413 with the three-field write error body."""
    response = client.post(
        PATH,
        content=_exactly(MAX_BODY_BYTES + 1),
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {
        "error": "PayloadTooLarge",
        "message": f"a write body may be at most {MAX_BODY_BYTES} bytes",
        "details": {"max_bytes": MAX_BODY_BYTES},
    }


@pytest.mark.usefixtures("project")
def test_a_lying_content_length_is_still_capped(app: Any, launch: Any) -> None:
    """A small Content-Length over a large body: 413 once the cap is passed."""
    data = _exactly(4 * MAX_BODY_BYTES)
    chunks = _split(data)
    status, body, read = _drive(
        app, _headers(launch, **{"content-length": "20"}), chunks
    )
    assert (status, body["error"]) == (413, "PayloadTooLarge")
    assert read == MAX_BODY_BYTES // CHUNK + 1 < len(chunks)


@pytest.mark.usefixtures("project")
def test_a_chunked_body_is_capped(app: Any, launch: Any) -> None:
    """No Content-Length, chunked: read until one chunk past the cap, then 413."""
    chunks = _split(_exactly(4 * MAX_BODY_BYTES))
    status, body, read = _drive(
        app, _headers(launch, **{"transfer-encoding": "chunked"}), chunks
    )
    assert (status, body["error"]) == (413, "PayloadTooLarge")
    assert read == MAX_BODY_BYTES // CHUNK + 1


@pytest.mark.usefixtures("project")
def test_an_oversized_content_length_is_refused_unread(app: Any, launch: Any) -> None:
    """A declared size over the cap is refused before any body is received."""
    chunks = _split(_exactly(2 * MAX_BODY_BYTES))
    headers = _headers(launch, **{"content-length": str(2 * MAX_BODY_BYTES)})
    status, _, read = _drive(app, headers, chunks)
    assert (status, read) == (413, 0)


@pytest.mark.parametrize("failing", ["cookie", "origin", "content-type"])
@pytest.mark.usefixtures("project")
def test_the_guard_refuses_before_the_body_is_read(
    app: Any, launch: Any, failing: str
) -> None:
    """An oversized body from a request the guard refuses: its refusal, zero reads."""
    headers = _headers(launch, cookie=failing != "cookie")
    if failing == "origin":
        headers = [(k, v) for k, v in headers if k != b"origin"]
    if failing == "content-type":
        headers = [
            (k, b"text/plain" if k == b"content-type" else v) for k, v in headers
        ]
    chunks = _split(_exactly(4 * MAX_BODY_BYTES))
    status, body, read = _drive(app, headers, chunks)
    expected = {"cookie": 401, "origin": 403, "content-type": 415}[failing]
    assert status == expected
    assert body["error"] != "PayloadTooLarge"
    assert read == 0
