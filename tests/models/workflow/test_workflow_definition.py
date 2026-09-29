"""The default workflow, and validation of a whole definition."""

import pytest
from pydantic import ValidationError

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition


def test_default_has_one_state_per_category_per_kind() -> None:
    """Work kinds get one state per category; backlog open, done, dropped."""
    definition = WorkflowDefinition.default()
    assert set(definition.kinds) == set(ItemKind)
    for kind in ItemKind:
        workflow = definition.for_kind(kind)
        categories = (
            [Category.OPEN, Category.DONE, Category.DROPPED]
            if kind is ItemKind.BACKLOG
            else list(Category)
        )
        assert [(s.name, s.category) for s in workflow.states] == [
            (c.value, c) for c in categories
        ]
        assert workflow.defaults == {
            Category.OPEN: "open",
            Category.DONE: "done",
            Category.DROPPED: "dropped",
        }
        assert workflow.transitions is None


def test_backlogged_is_no_longer_a_category() -> None:
    """Backlog is an item kind now; the old category is gone."""
    assert "backlogged" not in {c.value for c in Category}


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
