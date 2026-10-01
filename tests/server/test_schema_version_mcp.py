"""A tool call on a database newer than SCHEMA_VERSION fails, safely named."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession


def test_tool_call_refuses_a_newer_database(
    harness: Any, newer_database: Callable[[], int]
) -> None:
    """The server opens the database per call and refuses it there."""
    newer_database()

    async def scenario(client: ClientSession) -> str:
        return await harness.error(client, "projects_list")

    assert harness.run(scenario) == (
        "Error executing tool projects_list: "
        "SchemaVersionError: the database was written by a newer xoot"
    )
