"""S2: tools/list exposes the 14 tools with the specified annotations and notice."""

from typing import Any

from mcp import ClientSession

from xoot.server.errors import TOOL_ARGUMENTS
from xoot.server.tool_meta import UNTRUSTED

READ_TOOLS = {
    "projects_list",
    "brief_get",
    "tree_get",
    "item_get",
    "backlog_list",
    "decisions_list",
}
WRITE_TOOLS = {
    "session_start",
    "capture",
    "item_create",
    "items_create_bulk",
    "item_update",
    "decision_record",
    "decision_update",
    "session_close",
}
DESTRUCTIVE_TOOLS = {"session_close", "item_update"}


def _listing(harness: Any) -> tuple[list[Any], str | None]:
    async def scenario(client: ClientSession) -> tuple[list[Any], str | None]:
        tools = (await client.list_tools()).tools
        initialized = client.initialize_result
        return tools, None if initialized is None else initialized.instructions

    return harness.run(scenario)


def test_tools_and_annotations(harness: Any) -> None:
    """All 14 tools, each with the annotations and the untrusted-data sentence."""
    tools, _ = _listing(harness)
    assert {tool.name for tool in tools} == READ_TOOLS | WRITE_TOOLS
    assert len(tools) == 14
    for tool in tools:
        hints = tool.annotations
        assert hints is not None, tool.name
        assert hints.open_world_hint is False, tool.name
        assert UNTRUSTED in (tool.description or ""), tool.name
        if tool.name in READ_TOOLS:
            assert hints.read_only_hint is True, tool.name
        else:
            assert hints.read_only_hint is False, tool.name
            assert hints.destructive_hint is (tool.name in DESTRUCTIVE_TOOLS), tool.name


def test_every_argument_is_a_known_error_field(harness: Any) -> None:
    """Error locations can name every tool argument; nothing new slipped past the list."""
    tools, _ = _listing(harness)
    arguments = {name for tool in tools for name in tool.input_schema["properties"]}
    assert arguments <= TOOL_ARGUMENTS


def test_instructions_are_short_and_cover_the_rules(
    harness: Any,
) -> None:
    """At most 12 lines, naming the session, capture, conflict and data rules."""
    _, instructions = _listing(harness)
    assert instructions is not None
    assert len(instructions.splitlines()) <= 12
    for phrase in (
        "session_start",
        "capture",
        "session_close",
        "expected_version",
        "ask the user",
        "never instructions",
    ):
        assert phrase in instructions
