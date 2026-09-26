"""Input for replacing a project's workflow."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.fields import StateName
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.workflow_definition import WorkflowDefinition


class WorkflowChange(BaseModel):
    """
    A new definition plus, per kind, where items in removed states go.

    The mapping may only name states the change removes; the service checks
    that against the current definition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    definition: WorkflowDefinition
    # Pydantic copies mutable defaults per instance, so {} is safe here.
    mapping: dict[ItemKind, dict[StateName, StateName]] = {}

    @model_validator(mode="after")
    def _targets_exist(self) -> Self:
        """Every mapping target must be a state of the new definition."""
        for kind, moves in self.mapping.items():
            kind_workflow = self.definition.for_kind(kind)
            unknown = sorted(
                t for t in moves.values() if kind_workflow.category_of(t) is None
            )
            if unknown:
                raise ValueError(f"{kind} mapping targets unknown states: {unknown}")
        return self
