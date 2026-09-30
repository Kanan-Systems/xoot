"""
The dashboard write path and a real MCP server process write one database
at the same time: no update is lost, and the item both change from the same
version gets exactly one winner and one conflict.
"""

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp import ClientSession
from starlette.testclient import TestClient

from xoot.dashboard.app import create_app
from xoot.dashboard.guard import cookie_name
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.lookups import require_item
from xoot.store.store import Store

EACH = 10
TOKEN = "race-token"
PORT = 7373
ORIGIN = f"http://xoot.localhost:{PORT}"
HEADERS = {"origin": ORIGIN, "content-type": "application/json"}


def _app(db_path: Path, tmp_path: Path) -> Any:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return create_app(db_path, TOKEN, PORT, static)


def _stored(store: Store, item: Item) -> tuple[str, int]:
    with store.read() as conn:
        row = require_item(conn, item.id)
    return row.title, row.version


def _clients(store: Store, item: Item) -> list[str]:
    with store.read() as conn:
        rows = conn.execute(
            "SELECT client FROM event WHERE entity_type = 'item' AND entity_id = ? "
            "AND action = 'update' ORDER BY id",
            (item.id,),
        ).fetchall()
    return [row[0] for row in rows]


def test_no_lost_update_and_one_winner(  # pylint: disable=too-many-locals
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    harness: Any,
    tmp_path: Path,
) -> None:
    """Each side updates its own items plus one shared item, all from version 1."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)

    def subtasks() -> list[Item]:
        return [
            make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
            for _ in range(EACH)
        ]

    dash_items, mcp_items = subtasks(), subtasks()
    contested = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    dash_plan = [*dash_items[: EACH // 2], contested, *dash_items[EACH // 2 :]]
    mcp_plan = [*mcp_items[: EACH // 2], contested, *mcp_items[EACH // 2 :]]
    app = _app(store.path, tmp_path)
    start = threading.Barrier(2)
    dash: dict[str, tuple[int, Any]] = {}

    def dashboard() -> None:
        with TestClient(app, base_url=ORIGIN) as client:
            client.cookies.set(cookie_name(PORT), TOKEN)
            start.wait(timeout=60)
            for item in dash_plan:
                body = {"expected_version": 1, "title": f"dash {item.key}"}
                response = client.patch(
                    f"/api/v1/projects/xoot/items/{item.key}",
                    content=json.dumps(body),
                    headers=HEADERS,
                )
                dash[item.key] = (response.status_code, response.json())

    async def scenario(session: ClientSession) -> dict[str, tuple[bool, str]]:
        results: dict[str, tuple[bool, str]] = {}
        start.wait(timeout=60)
        for item in mcp_plan:
            result = await session.call_tool(
                "item_update",
                {
                    "project": "xo",
                    "key": item.key,
                    "expected_version": 1,
                    "changes": {"title": f"mcp {item.key}"},
                },
            )
            text = result.content[0].text if result.is_error else ""
            results[item.key] = (result.is_error, text)
        return results

    worker = threading.Thread(target=dashboard)
    worker.start()
    try:
        mcp = harness.run(scenario)
    finally:
        worker.join(timeout=120)
    assert not worker.is_alive()

    for item in dash_items:
        assert dash[item.key][0] == 200, dash[item.key]
        assert _stored(store, item) == (f"dash {item.key}", 2)
        assert _clients(store, item) == ["dashboard"]
    for item in mcp_items:
        assert mcp[item.key] == (False, "")
        assert _stored(store, item) == (f"mcp {item.key}", 2)
        assert _clients(store, item) == ["code"]

    dash_won = dash[contested.key][0] == 200
    mcp_won = not mcp[contested.key][0]
    assert dash_won != mcp_won
    if dash_won:
        assert "VersionConflictError" in mcp[contested.key][1]
        assert _stored(store, contested) == (f"dash {contested.key}", 2)
        assert _clients(store, contested) == ["dashboard"]
    else:
        status, payload = dash[contested.key]
        assert status == 409
        assert payload["error"] == "VersionConflictError"
        assert payload["details"]["actors"] == [{"kind": "claude", "client": "code"}]
        assert _stored(store, contested) == (f"mcp {contested.key}", 2)
        assert _clients(store, contested) == ["code"]
