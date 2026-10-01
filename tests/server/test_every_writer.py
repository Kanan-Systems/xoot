"""
One event from every client (chat, code, paste, cli, dashboard) and every
actor (claude, user, system), each through its real write path, read back
through the Event model, MCP item_get and the dashboard item endpoint. A
reader that cannot read a writer's events fails here, which is the batch-8
"invalid arguments: * (enum)" failure seen from the reading side.
"""

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from starlette.testclient import TestClient

from xoot.cli import console
from xoot.cli.__main__ import main
from xoot.dashboard.app import create_app
from xoot.dashboard.guard import cookie_name
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.store.store import Store

TOKEN = "writer-token-8Hd2q"
PORT = 7374
ORIGIN = f"http://xoot.localhost:{PORT}"

# Who writes what: goal-1 (code, then the CLI's redaction), goal-2 (chat),
# goal-3 and its batch (paste, then the system completing them), goal-4
# (dashboard).
KEYS = ("goal-1", "goal-2", "goal-3", "goal-3/batch-1", "goal-4")
EXPECTED = {
    ("claude", "code"),
    ("claude", "chat"),
    ("claude", "paste"),
    ("system", "paste"),
    ("user", "cli"),
    ("user", "dashboard"),
}

type Who = set[tuple[str, str]]


def _who(events: list[dict[str, Any]]) -> Who:
    return {(event["actor_kind"], event["client"]) for event in events}


def _mcp_create(harness: Any, client_name: str, title: str) -> str:
    async def scenario(client: ClientSession) -> Any:
        return await harness.ok(
            client, "item_create", project="xoot", kind="goal", title=title
        )

    return str(harness.run(scenario, client_name=client_name)["item"]["key"])


def _paste_block() -> bytes:
    ops = [
        {"op": "item_create", "ref": "g", "kind": "goal", "title": "pasted"},
        {"op": "item_create", "ref": "b", "kind": "batch", "title": "b", "parent": "$g"},
        {"op": "item_create", "ref": "t", "kind": "subtask", "title": "t",
         "parent": "$b"},
        {"op": "item_update", "key": "$t", "changes": {"state": "done"}},
    ]  # fmt: skip
    block = {"xoot": 2, "project": "xoot", "ops": ops}
    return f"```xoot\n{json.dumps(block)}\n```\n".encode()


@pytest.fixture(name="dashboard")
def fixture_dashboard(db_path: Path, tmp_path: Path) -> Any:
    """The dashboard app on the test database, holding the token cookie."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(db_path, TOKEN, PORT, static)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.cookies.set(cookie_name(PORT), TOKEN)
        yield client


@pytest.fixture(name="cli")
def fixture_cli(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Callable[..., int]:
    """Factory: run `xoot --db <test db> ARGS` in-process with stdin bytes and
    no terminal, returning the exit code."""

    def run(*argv: str, stdin: bytes = b"") -> int:
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin)))
        monkeypatch.setattr(console, "TTY_PATH", str(db_path.parent / "no-tty"))
        code = main(["--db", str(db_path), *argv])
        capsys.readouterr()
        return code

    return run


def _write_from_every_client(
    harness: Any, cli: Callable[..., int], dashboard: TestClient
) -> None:
    assert _mcp_create(harness, "claude-code", "by code") == "goal-1"
    assert _mcp_create(harness, "claude-ai", "by chat") == "goal-2"
    assert cli("paste", "apply", "-", "--yes", stdin=_paste_block()) == 0
    assert cli("redact", "xoot:goal-1", "title", "--yes") == 0
    created = dashboard.post(
        "/api/v1/projects/xoot/items",
        content=json.dumps({"kind": "goal", "title": "by dashboard"}),
        headers={"origin": ORIGIN, "content-type": "application/json"},
    )
    assert created.status_code == 201, created.text


def _read_over_mcp(harness: Any) -> Who:
    async def item_gets(client: ClientSession) -> list[Any]:
        return [
            await harness.ok(client, "item_get", project="xoot", key=key)
            for key in KEYS
        ]

    seen: Who = set()
    for output in harness.run(item_gets):
        seen |= _who(output["events"])
    return seen


def _read_over_dashboard(dashboard: TestClient) -> Who:
    seen: Who = set()
    for key in KEYS:
        response = dashboard.get(f"/api/v1/projects/xoot/items/{key}")
        assert response.status_code == 200, response.text
        seen |= _who(response.json()["events"])
    return seen


def test_every_writer_is_read_by_every_reader(
    harness: Any,
    store: Store,
    project: Project,
    dashboard: TestClient,
    cli: Callable[..., int],
) -> None:
    """Six writer identities in, the same six out of each reader."""
    _write_from_every_client(harness, cli, dashboard)
    with store.read() as conn:
        events = event_db.list_for_project(conn, project.id)
    stored = {(event.actor_kind.value, event.client.value) for event in events}
    assert stored == EXPECTED
    assert {client for _, client in stored} == {c.value for c in Client}
    assert {actor for actor, _ in stored} == {a.value for a in ActorKind}
    assert _read_over_mcp(harness) == EXPECTED
    assert _read_over_dashboard(dashboard) == EXPECTED
