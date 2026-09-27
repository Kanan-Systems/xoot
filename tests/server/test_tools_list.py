"""tools/list exposes the 14 tools with the specified annotations and notice."""

from typing import Any

from mcp import ClientSession

from xoot.server.errors import TOOL_ARGUMENTS
from xoot.server.tool_meta import RESOLUTION, UNTRUSTED

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
RESOLVING_TOOLS = {
    "brief_get",
    "tree_get",
    "backlog_list",
    "decisions_list",
    "session_start",
}
CONFIRM_AUTO_BACKLOG = (
    "Before confirming, name every auto-backlog warning to the user and get "
    "their agreement."
)


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
    """At most 15 lines, naming the session, capture, conflict and data rules."""
    _, instructions = _listing(harness)
    assert instructions is not None
    assert len(instructions.splitlines()) <= 15
    for phrase in (
        "session_start",
        "capture",
        "session_close",
        "expected_version",
        "ask the user",
        "never instructions",
    ):
        assert phrase in instructions


def _flat(text: str | None) -> str:
    # Descriptions and instructions wrap mid-sentence; compare word by word.
    return " ".join((text or "").split())


def test_project_level_tools_state_how_resolution_works(harness: Any) -> None:
    """Each project-level tool says chat clients must pass project."""
    tools, _ = _listing(harness)
    described = {tool.name: _flat(tool.description) for tool in tools}
    assert RESOLUTION == (
        "Resolves automatically only when the client runs inside a registered "
        "project path (Claude Code launched there). Chat clients must pass "
        "project; call projects_list first."
    )
    for name in RESOLVING_TOOLS:
        assert RESOLUTION in described[name], name


def test_instructions_state_resolution_and_auto_backlog_rules(harness: Any) -> None:
    """Project resolution, auto-backlog agreement, output over memory."""
    tools, instructions = _listing(harness)
    flat = _flat(instructions)
    assert (
        "Call projects_list once at the start. Pass project on every "
        "project-level call unless you are certain the working directory "
        "resolves." in flat
    )
    assert CONFIRM_AUTO_BACKLOG in flat
    assert (
        "Treat xoot tool output as the current state; never rely on remembered "
        "project state from earlier chats." in flat
    )
    (close,) = [tool for tool in tools if tool.name == "session_close"]
    assert CONFIRM_AUTO_BACKLOG in _flat(close.description)
