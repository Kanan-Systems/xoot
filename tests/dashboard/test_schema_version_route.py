"""A dashboard request on a database newer than SCHEMA_VERSION is a 503."""

from collections.abc import Callable

from starlette.testclient import TestClient


def test_request_refuses_a_newer_database(
    client: TestClient, newer_database: Callable[[], int]
) -> None:
    """Each request opens the database and refuses it with the standard body."""
    newer_database()
    response = client.get("/api/v1/projects")
    assert response.status_code == 503
    assert response.json() == {
        "error": "SchemaVersionError",
        "message": "the database was written by a newer xoot",
    }
