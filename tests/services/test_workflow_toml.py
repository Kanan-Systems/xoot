"""Workflow definitions round-trip through the hand-written TOML."""

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from xoot.exceptions.workflow_file_error import WorkflowFileError
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.state_spec import StateSpec
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.workflow_toml import (
    MAX_BYTES,
    basic_string,
    dump_workflow,
    load_workflow,
    read_workflow_file,
)

CUSTOM_STATES = (
    ("todo", Category.OPEN),
    ("triage", Category.OPEN),
    ("doing", Category.ACTIVE),
    ("review", Category.ACTIVE),
    ("stuck", Category.BLOCKED),
    ("asked", Category.AWAITING_INPUT),
    ("shipped", Category.DONE),
    ("abandoned", Category.DROPPED),
    ("later", Category.BACKLOGGED),
)


def custom_definition() -> WorkflowDefinition:
    """Renamed states, several per category, restricted transitions on goals."""
    states = tuple(StateSpec(name=n, category=c) for n, c in CUSTOM_STATES)
    defaults = {
        Category.OPEN: "todo",
        Category.BACKLOGGED: "later",
        Category.DROPPED: "abandoned",
    }
    restricted = KindWorkflow(
        states=states,
        defaults=defaults,
        transitions={"todo": ("doing", "abandoned"), "doing": ("review",), "later": ()},
    )
    free = KindWorkflow(states=states, defaults=defaults)
    return WorkflowDefinition(
        kinds={ItemKind.GOAL: restricted, ItemKind.BATCH: free, ItemKind.SUBTASK: free}
    )


@pytest.mark.parametrize(
    "definition", [WorkflowDefinition.default(), custom_definition()]
)
def test_round_trip(definition: WorkflowDefinition) -> None:
    """export -> tomllib -> model is the same definition, restrictions included."""
    text = dump_workflow(definition)
    assert WorkflowDefinition.model_validate(tomllib.loads(text)) == definition
    assert load_workflow(text.encode()) == definition


def test_structure_matches_the_format() -> None:
    """Tables per kind, states as an array of tables, transitions only if set."""
    document = tomllib.loads(dump_workflow(custom_definition()))
    goal = document["kinds"]["goal"]
    assert set(document) == {"kinds"}
    assert goal["states"][0] == {"name": "todo", "category": "open"}
    assert goal["defaults"]["open"] == "todo"
    assert goal["transitions"]["later"] == []
    assert "transitions" not in document["kinds"]["batch"]


@pytest.mark.parametrize(
    "text",
    [
        '[kinds.goal]\nextra = "x"\n',
        '[kinds.goal]\n[[kinds.goal.states]]\nname = "BAD NAME"\ncategory = "open"\n',
        "other = 1\n",
    ],
)
def test_invalid_definitions_are_refused(text: str) -> None:
    """Anything outside the structure fails WorkflowDefinition validation."""
    with pytest.raises(ValidationError):
        load_workflow(text.encode())


@pytest.mark.parametrize("data", [b"[kinds\n", b"\xff\xfe", b"x" * (MAX_BYTES + 1)])
def test_unreadable_data_is_refused(data: bytes) -> None:
    """Broken TOML, non-UTF-8 bytes and an oversized document."""
    with pytest.raises(WorkflowFileError):
        load_workflow(data)


def test_file_limits(tmp_path: Path) -> None:
    """Over 64 KiB, a directory or a missing file is refused; the limit itself is fine."""
    padded = tmp_path / "padded.toml"
    text = dump_workflow(WorkflowDefinition.default())
    padded.write_text(text + "#" * (MAX_BYTES - len(text) - 1) + "\n")
    assert padded.stat().st_size == MAX_BYTES
    assert read_workflow_file(padded) == WorkflowDefinition.default()
    padded.write_text(text + "#" * (MAX_BYTES - len(text)) + "\n")
    for path in (padded, tmp_path, tmp_path / "missing.toml"):
        with pytest.raises(WorkflowFileError):
            read_workflow_file(path)


@pytest.mark.parametrize(
    "value",
    ["plain", 'q"uote', "back\\slash", "tab\tnew\nline\r", "\x00\x1b\x7f", "caf\u00e9"],
)
def test_basic_strings_parse_back(value: str) -> None:
    """Quotes, backslashes and control characters survive a TOML parse."""
    assert tomllib.loads(f"v = {basic_string(value)}")["v"] == value
