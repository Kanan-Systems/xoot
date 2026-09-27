"""The default workflow, and validation of a whole definition."""

import pytest
from pydantic import ValidationError

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition


def test_default_has_one_state_per_category_per_kind() -> None:
    """Every kind gets one state per category, named after it, unrestricted."""
    definition = WorkflowDefinition.default()
    assert set(definition.kinds) == set(ItemKind)
    for kind in ItemKind:
        workflow = definition.for_kind(kind)
        assert [(s.name, s.category) for s in workflow.states] == [
            (c.value, c) for c in Category
        ]
        assert workflow.defaults == {
            Category.OPEN: "open",
            Category.BACKLOGGED: "backlogged",
            Category.DROPPED: "dropped",
        }
        assert workflow.transitions is None


def test_every_kind_is_required() -> None:
    """A definition missing a kind is rejected."""
    kinds = WorkflowDefinition.default().model_dump()["kinds"]
    del kinds[ItemKind.SUBTASK]
    with pytest.raises(ValidationError, match="subtask"):
        WorkflowDefinition.model_validate({"kinds": kinds})


def test_round_trips_through_json() -> None:
    """The stored JSON form validates back to the same definition."""
    definition = WorkflowDefinition.default()
    assert (
        WorkflowDefinition.model_validate_json(definition.model_dump_json())
        == definition
    )
