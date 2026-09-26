"""Workflow change inputs: mapping targets must exist in the new definition."""

import pytest
from pydantic import ValidationError

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition


def test_mapping_to_known_state_is_accepted() -> None:
    """A target that exists for that kind is fine."""
    change = WorkflowChange(
        definition=WorkflowDefinition.default(),
        mapping={ItemKind.GOAL: {"review": "active"}},
    )
    assert change.mapping[ItemKind.GOAL] == {"review": "active"}


def test_mapping_to_unknown_state_is_rejected() -> None:
    """A target the new definition lacks is rejected up front."""
    with pytest.raises(ValidationError, match="unknown states"):
        WorkflowChange(
            definition=WorkflowDefinition.default(),
            mapping={ItemKind.GOAL: {"review": "ghost"}},
        )
