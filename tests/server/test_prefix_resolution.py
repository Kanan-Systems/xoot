"""B1/B5 through MCP: a key prefix resolves like an alias and is reported as
"prefix", the unresolved error lists prefixes too, and projects_list reports
paths."""

from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.actor import Actor
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.project_service import register_project
from xoot.store.store import Store


@pytest.fixture(name="named", autouse=True)
def fixture_named(store: Store, user: Actor) -> None:
    """One project with only a prefix, one with an alias and a path."""
    register_project(store, ProjectRegistration(key_prefix="bare", name="b"), user)
    register_project(
        store,
        ProjectRegistration(
            key_prefix="named", name="n", aliases=("nm",), paths=("/x/named",)
        ),
        user,
    )


def test_prefix_resolves_and_errors_list_every_name(
    tmp_path: Path, harness: Any
) -> None:
    """brief_get by prefix; an unknown name lists prefixes and aliases."""

    async def scenario(client: ClientSession) -> tuple[Any, ...]:
        return (
            await harness.ok(client, "brief_get", project="bare"),
            await harness.ok(client, "tree_get", project="named"),
            await harness.ok(client, "tree_get", project="nm"),
            await harness.error(client, "brief_get", project="nope"),
            await harness.ok(client, "projects_list"),
        )

    brief, tree, by_alias, error, listing = harness.run(scenario, cwd=tmp_path)
    assert (brief["project"]["key_prefix"], brief["resolved_by"]) == ("bare", "prefix")
    assert (tree["project"], tree["resolved_by"]) == ("named", "prefix")
    assert (by_alias["project"], by_alias["resolved_by"]) == ("named", "alias")
    assert error.endswith(
        "project not resolved; pass project=<alias or prefix>, "
        "one of: bare, named, nm"
    )
    assert [p["paths"] for p in listing["projects"]] == [[], ["/x/named"]]
