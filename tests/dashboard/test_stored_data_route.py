"""The item endpoint over an event this code cannot read is a 500 with the
standard error body naming the stored data."""

from collections.abc import Callable
from typing import Any

from starlette.testclient import TestClient

from xoot.exceptions.stored_data_error import RESTART_HINT
from xoot.models.item.item import Item


def test_item_endpoint_reports_unreadable_stored_data(
    client: TestClient, seeded: Any, foreign_event: Callable[[Item], int]
) -> None:
    """Not a 400 "invalid arguments", not a 503 "database could not serve"."""
    event_id = foreign_event(seeded.goal)
    response = client.get(f"/api/v1/projects/xoot/items/{seeded.goal.key}")
    assert response.status_code == 500
    assert response.json() == {
        "error": "StoredDataError",
        "message": (
            f"stored data could not be read: event row {event_id}, field client: "
            f"unexpected value 'telepathy'; {RESTART_HINT}"
        ),
    }
