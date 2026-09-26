"""A complete workflow definition covering every item kind."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.state_spec import StateSpec


class WorkflowDefinition(BaseModel):
    """
    One KindWorkflow per item kind. Stored as JSON on each workflow version.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kinds: dict[ItemKind, KindWorkflow]

    @model_validator(mode="after")
    def _every_kind(self) -> Self:
        """Require a workflow for every item kind."""
        missing = sorted(set(ItemKind) - self.kinds.keys())
        if missing:
            raise ValueError(f"missing workflows for kinds: {', '.join(missing)}")
        return self

    @classmethod
    def default(cls) -> Self:
        """
        Build the shipped default: per kind, one state per category, named
        after the category, with no transition restrictions.

        Returns:
            - definition (WorkflowDefinition): the default definition.
        """
        kind_workflow = KindWorkflow(
            states=tuple(StateSpec(name=c.value, category=c) for c in Category),
            defaults={
                c: c.value
                for c in (Category.OPEN, Category.BACKLOGGED, Category.DROPPED)
            },
        )
        return cls(kinds={kind: kind_workflow for kind in ItemKind})

    def for_kind(self, kind: ItemKind) -> KindWorkflow:
        """
        Return the workflow for one item kind.

        Args:
            - kind (ItemKind): the item kind.

        Returns:
            - workflow (KindWorkflow): that kind's states and rules.
        """
        return self.kinds[kind]
