"""
Fixtures for the dashboard tests: the app on the test database (always under
tmp_path), a client that already holds the per-port cookie, and a seeded
project.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from xoot.dashboard.app import create_app
from xoot.dashboard.guard import cookie_name
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.services.decision_service import create_decision
from xoot.services.item_service import update_item
from xoot.store.store import Store

TOKEN = "test-token-4Qw9dZ"
PORT = 7373
ORIGIN = f"http://xoot.localhost:{PORT}"
INDEX = "<!doctype html><title>xoot</title>"


@dataclass(frozen=True)
class Launch:
    """The token, port and origin the test app was built with."""

    token: str
    port: int
    origin: str


@dataclass(frozen=True)
class Seeded:
    """The seeded project's records."""

    goal: Item
    batch: Item
    subtask: Item
    held: Item
    decision_key: str


@pytest.fixture(name="launch")
def fixture_launch() -> Launch:
    """The launch values: tests import nothing from conftest."""
    return Launch(TOKEN, PORT, ORIGIN)


@pytest.fixture(name="static_dir")
def fixture_static_dir(tmp_path: Path) -> Path:
    """A stand-in bundle: an index page and one asset."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(INDEX, encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1);", encoding="utf-8")
    return static


@pytest.fixture(name="anonymous")
def fixture_anonymous(
    store: Store, db_path: Path, static_dir: Path
) -> Iterator[TestClient]:
    """A client with no cookie, sending the allowed Host."""
    assert store.path == db_path
    app = create_app(db_path, TOKEN, PORT, static_dir)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield client


@pytest.fixture(name="client")
def fixture_client(anonymous: TestClient) -> TestClient:
    """A client holding a valid token cookie."""
    anonymous.cookies.set(cookie_name(PORT), TOKEN)
    return anonymous


@pytest.fixture(name="seeded")
def fixture_seeded(
    store: Store,
    ctx: WriteContext,
    project: Project,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
) -> Seeded:
    """goal-1 > batch-1 > a done subtask, a backlog item held on the batch
    (which blocks it), and a decision made on the batch."""
    goal = make_item(project, ItemKind.GOAL, title="goal", body="<b>body</b>")
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    held = capture_on(subtask, "held", "why")
    subtask = update_item(store, subtask.id, 1, ItemUpdate(state="done"), ctx)[0]
    decision = create_decision(
        store,
        project.id,
        DecisionCreate(owner_item_id=batch.id, title="d", body="decision body"),
        ctx,
    )
    return Seeded(goal, batch, subtask, held, decision.key)
