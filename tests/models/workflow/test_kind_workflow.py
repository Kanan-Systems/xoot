"""Model side: invalid kind workflows are rejected."""

from typing import Any

import pytest
from pydantic import ValidationError

from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow


def _valid() -> dict[str, Any]:
    return {
        "states": [
            {"name": "todo", "category": "open"},
            {"name": "doing", "category": "active"},
            {"name": "shipped", "category": "done"},
            {"name": "gone", "category": "dropped"},
        ],
        "defaults": {"open": "todo", "done": "shipped", "dropped": "gone"},
    }


def test_valid_workflow() -> None:
    """A consistent workflow validates and answers category questions."""
    workflow = KindWorkflow.model_validate(_valid())
    assert workflow.category_of("doing") is Category.ACTIVE
    assert workflow.category_of("nope") is None
    assert workflow.default_state(Category.DONE) == "shipped"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"states": []}, "at least 1"),
        (
            {"states": [{"name": "todo", "category": "open"}] * 2},
            "unique",
        ),
        ({"defaults": {"open": "todo", "dropped": "gone"}}, "done"),
        (
            {"defaults": {"open": "doing", "done": "shipped", "dropped": "gone"}},
            "not in the open category",
        ),
        (
            {"defaults": {"open": "ghost", "done": "shipped", "dropped": "gone"}},
            "not in the open category",
        ),
        ({"states": [{"name": "icebox", "category": "backlogged"}]}, "category"),
        ({"transitions": {"todo": ["ghost"]}}, "unknown states"),
        ({"states": [{"name": "x", "category": "someday"}]}, "category"),
    ],
)
def test_invalid_workflows_are_rejected(change: dict[str, Any], message: str) -> None:
    """Duplicates, missing or mismatched defaults and unknown names fail."""
    with pytest.raises(ValidationError, match=message):
        KindWorkflow.model_validate({**_valid(), **change})


def test_transitions_absent_means_any_move() -> None:
    """Without transitions every move is allowed."""
    workflow = KindWorkflow.model_validate(_valid())
    assert workflow.allows("todo", "gone")
    assert workflow.allows("gone", "todo")


def test_transitions_restrict_moves() -> None:
    """With transitions only listed moves (and staying put) are allowed."""
    workflow = KindWorkflow.model_validate(
        {**_valid(), "transitions": {"todo": ["doing"]}}
    )
    assert workflow.allows("todo", "doing")
    assert workflow.allows("doing", "doing")
    assert not workflow.allows("todo", "gone")
    assert not workflow.allows("doing", "todo")
