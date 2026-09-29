"""Each API request opens its own Store on a worker thread and closes it."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from xoot.dashboard import reads
from xoot.store.store import Store

# Taken before any patching, so the recorder can call the real one.
REAL_OPEN = Store.open


@dataclass
class Recorded:
    """Every Store the dashboard opened, with its thread, and those closed."""

    opened: list[tuple[Store, int]] = field(default_factory=list)
    closed: list[Store] = field(default_factory=list)


@pytest.fixture(name="recorder")
def fixture_recorder(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    """Route the dashboard's Store.open through a recorder."""
    recorded = Recorded()

    def recording_open(path: Path) -> Store:
        store = REAL_OPEN(path)
        real_close = store.close

        def close() -> None:
            recorded.closed.append(store)
            real_close()

        store.close = close  # type: ignore[method-assign]
        recorded.opened.append((store, threading.get_ident()))
        return store

    monkeypatch.setattr(reads.Store, "open", recording_open)
    return recorded


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/projects",
        "/api/v1/projects/xoot/brief",
        "/api/v1/projects/xoot/tree",
        "/api/v1/projects/xoot/changes",
        "/api/v1/projects/xoot/items/goal-1/batch-1",
        "/api/v1/projects/xoot/items/goal-99",
    ],
)
def test_one_store_per_request_closed_before_the_reply(
    client: TestClient, seeded: Any, recorder: Recorded, path: str
) -> None:
    """Two requests: two stores, both closed, none on the event-loop thread."""
    assert seeded
    loop_thread = threading.get_ident()
    for _ in range(2):
        client.get(path)
    assert len(recorder.opened) == 2
    assert [store for store, _ in recorder.opened] == recorder.closed
    assert recorder.opened[0][0] is not recorder.opened[1][0]
    assert all(thread != loop_thread for _, thread in recorder.opened)


def test_refused_requests_open_no_store(
    anonymous: TestClient, recorder: Recorded
) -> None:
    """The guard refuses before any database work."""
    anonymous.get("/api/v1/projects")
    anonymous.post("/api/v1/projects")
    anonymous.get("/api/v1/projects/xoot/tree?depth=99")
    assert not recorder.opened
