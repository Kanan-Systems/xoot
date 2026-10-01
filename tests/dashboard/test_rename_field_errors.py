"""A refused dashboard rename names the field, name or alias, not "*"."""

import json
from typing import Any

import pytest
from starlette.testclient import TestClient


@pytest.mark.parametrize(
    ("body", "location"),
    [
        ({"name": ""}, "name (string_too_short)"),
        ({"name": "x" * 201}, "name (string_too_long)"),
        ({"alias": "Not A Slug"}, "alias (string_pattern_mismatch)"),
        ({"alias": "goal-12"}, "alias (key_shaped_alias)"),
    ],
)
def test_rename_refusal_names_the_field(
    client: TestClient, launch: Any, project: Any, body: Any, location: str
) -> None:
    """422 with the field's name; nothing renamed."""
    response = client.patch(
        "/api/v1/projects/xoot",
        content=json.dumps(body),
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 422, response.text
    error = response.json()
    assert error["error"] == "ValidationError"
    assert error["message"] == f"invalid arguments: {location}"
    assert client.get("/api/v1/projects").json()["projects"][0]["name"] == project.name


def test_unknown_fields_stay_masked(
    client: TestClient, launch: Any, project: Any
) -> None:
    """Caller-chosen keys are still never echoed."""
    assert project.key_prefix == "xoot"
    response = client.patch(
        "/api/v1/projects/xoot",
        content=json.dumps({"name": "n", "secret-key": 1}),
        headers={"origin": launch.origin, "content-type": "application/json"},
    )
    assert response.status_code == 422
    assert "secret-key" not in response.text
    assert response.json()["message"] == "invalid arguments: * (extra_forbidden)"
