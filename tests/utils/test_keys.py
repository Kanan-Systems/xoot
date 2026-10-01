"""The key grammar: every item and decision shape, qualified keys, refusals."""

import pytest

from xoot.utils.keys import (
    child_key,
    decision_key,
    is_decision_key,
    is_item_key,
    is_key,
    parse_decision_key,
    parse_item_key,
    rebase_key,
    split_qualified,
)

ITEM_SHAPES = {
    "goal-1": (("goal", 1),),
    "goal-1/batch-2": (("goal", 1), ("batch", 2)),
    "goal-1/batch-2/subtask-3": (("goal", 1), ("batch", 2), ("subtask", 3)),
    "backlog-4": (("backlog", 4),),
    "goal-1/backlog-5": (("goal", 1), ("backlog", 5)),
    "goal-1/batch-2/backlog-6": (("goal", 1), ("batch", 2), ("backlog", 6)),
}
DECISION_SHAPES = {
    "goal-1/decision-1": ("goal-1", 1),
    "goal-1/batch-2/decision-3": ("goal-1/batch-2", 3),
    "goal-1/batch-2/subtask-3/decision-12": ("goal-1/batch-2/subtask-3", 12),
}
INVALID = [
    "",
    "goal",
    "goal-0",
    "goal-01",
    "goal-1/",
    "/goal-1",
    "goal-1//batch-2",
    "Goal-1",
    "goal-1/subtask-2",
    "batch-1",
    "subtask-1",
    "goal-1/batch-2/subtask-3/backlog-4",
    "backlog-1/batch-2",
    "goal-1/goal-2",
    "goal-1/batch-2/subtask-3/subtask-4",
    "xoot-12",
    "goal-99999999999999999999",
    "goal-1 ",
    "goal-1\n",
]
INVALID_DECISIONS = [
    "decision-1",
    "backlog-1/decision-1",
    "goal-1/backlog-2/decision-1",
    "goal-1/decision-0",
    "goal-1/decision-1/decision-2",
]


@pytest.mark.parametrize(("key", "segments"), ITEM_SHAPES.items())
def test_every_item_shape_parses(
    key: str, segments: tuple[tuple[str, int], ...]
) -> None:
    """The six item shapes parse to their segments and are not decisions."""
    assert parse_item_key(key) == segments
    assert is_item_key(key) and is_key(key)
    assert parse_decision_key(key) is None


@pytest.mark.parametrize(("key", "parts"), DECISION_SHAPES.items())
def test_every_decision_shape_parses(key: str, parts: tuple[str, int]) -> None:
    """A decision key is its owner's key plus decision-<n>."""
    assert parse_decision_key(key) == parts
    assert is_decision_key(key) and is_key(key)
    assert parse_item_key(key) is None


@pytest.mark.parametrize("key", INVALID)
def test_invalid_item_keys_are_refused(key: str) -> None:
    """Anything off the grammar, or beyond a stored id, is not a key."""
    assert parse_item_key(key) is None
    assert not is_item_key(key)


@pytest.mark.parametrize("key", INVALID_DECISIONS)
def test_invalid_decision_keys_are_refused(key: str) -> None:
    """Decisions sit on goals, batches or subtasks only, numbered from 1."""
    assert parse_decision_key(key) is None
    assert not is_decision_key(key)


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("xoot:goal-1", ("xoot", "goal-1")),
        ("ab:goal-1/batch-2/decision-3", ("ab", "goal-1/batch-2/decision-3")),
        ("goal-1", (None, "goal-1")),
    ],
)
def test_qualified_keys_split(text: str, parts: tuple[str | None, str]) -> None:
    """A <prefix>: qualifier splits off; an unqualified key has none."""
    assert split_qualified(text) == parts
    assert is_key(text)


@pytest.mark.parametrize(
    "text",
    ["X:goal-1", "a:goal-1", "xo-t:goal-1", ":goal-1", "xoot:", "xoot:xoot:goal-1"],
)
def test_malformed_qualifiers_are_refused(text: str) -> None:
    """A qualifier must be a well-formed prefix followed by one key."""
    assert not is_key(text)


def test_builders_follow_the_grammar() -> None:
    """child_key and decision_key build keys the parsers accept, qualified too."""
    batch = child_key("goal-1", "batch", 2)
    assert batch == "goal-1/batch-2"
    assert child_key(None, "goal", 3) == "goal-3"
    assert child_key(None, "backlog", 1) == "backlog-1"
    assert decision_key(batch, 4) == "goal-1/batch-2/decision-4"
    for key in (batch, decision_key(batch, 4), f"xoot:{batch}"):
        assert is_key(key)


def test_rebase_moves_keys_under_a_new_root() -> None:
    """A moved root's descendants keep their tail and take the new head."""
    assert rebase_key("goal-1/batch-2", "goal-1/batch-2", "goal-3/batch-7") == (
        "goal-3/batch-7"
    )
    assert rebase_key(
        "goal-1/batch-2/subtask-4", "goal-1/batch-2", "goal-3/batch-7"
    ) == ("goal-3/batch-7/subtask-4")
    with pytest.raises(ValueError):
        rebase_key("goal-1/batch-20", "goal-1/batch-2", "goal-3/batch-7")
