"""
The dashboard API's project segment takes a key prefix or an alias, by the
MCP project argument's rule; anything else is the standard 404.
"""

from typing import Any

import pytest
from starlette.testclient import TestClient


@pytest.mark.parametrize("name", ["xoot", "xo"], ids=["prefix", "alias"])
def test_prefix_and_alias_open_the_same_project(
    client: TestClient, seeded: Any, name: str
) -> None:
    """Every read answers for the project, and names it by its prefix."""
    tree = client.get(f"/api/v1/projects/{name}/tree")
    assert tree.status_code == 200, tree.text
    assert tree.json()["project"] == "xoot"
    item = client.get(f"/api/v1/projects/{name}/items/{seeded.goal.key}")
    assert item.status_code == 200, item.text
    assert item.json()["item"]["key"] == seeded.goal.key


@pytest.mark.parametrize(
    ("name", "shown"),
    [("nope", "nope"), ("Not%20A%20Slug", "malformed key")],
    ids=["unknown", "malformed"],
)
def test_unknown_name_is_a_404(client: TestClient, name: str, shown: str) -> None:
    """A name that is neither a prefix nor an alias is not found."""
    assert client.get("/api/v1/projects").status_code == 200
    response = client.get(f"/api/v1/projects/{name}/tree")
    assert response.status_code == 404
    assert response.json() == {
        "error": "NotFoundError",
        "message": f"not found: {shown}",
    }
