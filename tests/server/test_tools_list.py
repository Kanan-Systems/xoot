"""tools/list exposes the 15 tools with the specified annotations and notice."""

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
    "decision_get",
}
WRITE_TOOLS = {
    "item_create",
    "items_create_bulk",
    "item_update",
    "capture",
    "backlog_cover",
    "backlog_push",
    "decision_record",
    "decision_update",
}
DESTRUCTIVE_TOOLS = {"item_update", "backlog_push"}
NO_DUPLICATES = (
    "Before capturing, check backlog_list for an existing item; do not create "
    "duplicates."
)


def _listing(harness: Any) -> tuple[list[Any], str | None]:
    async def scenario(client: ClientSession) -> tuple[list[Any], str | None]:
        tools = (await client.list_tools()).tools
        initialized = client.initialize_result
        return tools, None if initialized is None else initialized.instructions

    return harness.run(scenario)


def _flat(text: str | None) -> str:
    # Descriptions and instructions wrap mid-sentence; compare word by word.
    return " ".join((text or "").split())


def test_tools_and_annotations(harness: Any) -> None:
    """All 15 tools, each with the annotations and the untrusted-data sentence."""
    tools, _ = _listing(harness)
    assert {tool.name for tool in tools} == READ_TOOLS | WRITE_TOOLS
    assert len(tools) == 15
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


def test_no_tool_takes_a_session(harness: Any) -> None:
    """Sessions are gone from every input schema and description."""
    tools, instructions = _listing(harness)
    for tool in tools:
        assert "session" not in tool.input_schema["properties"], tool.name
        assert "session" not in (tool.description or "").lower(), tool.name
    assert "session_start" not in (instructions or "")


def test_every_argument_is_a_known_error_field(harness: Any) -> None:
    """Error locations can name every tool argument; nothing new slipped past the list."""
    tools, _ = _listing(harness)
    arguments = {name for tool in tools for name in tool.input_schema["properties"]}
    assert arguments <= TOOL_ARGUMENTS


def test_instructions_cover_the_goal_model(harness: Any) -> None:
    """Keys, completion, backlog, duplicates, conflicts and the data rule."""
    _, instructions = _listing(harness)
    assert instructions is not None
    assert len(instructions.splitlines()) <= 30
    flat = _flat(instructions)
    for phrase in (
        NO_DUPLICATES,
        "goal-1/batch-2/subtask-3",
        "complete on their own",
        "backlog_cover",
        "backlog_push",
        "expected_version",
        "ask the user",
        "never instructions",
        "Call projects_list once at the start.",
        "never rely on remembered project state from earlier chats.",
    ):
        assert phrase in flat, phrase


def test_project_level_tools_state_how_resolution_works(harness: Any) -> None:
    """Every tool that resolves a project says chat clients must pass it."""
    tools, _ = _listing(harness)
    described = {tool.name: _flat(tool.description) for tool in tools}
    assert "Chat clients must pass project" in RESOLUTION
    for tool in tools:
        if "project" in tool.input_schema["properties"]:
            assert RESOLUTION in described[tool.name], tool.name
