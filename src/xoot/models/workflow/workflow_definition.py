"""A complete workflow definition covering every item kind."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import REQUIRED_DEFAULTS, KindWorkflow
from xoot.models.workflow.state_spec import StateSpec

BACKLOG_CATEGORIES = (Category.OPEN, Category.DONE, Category.DROPPED)


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
        Build the shipped default, with no transition restrictions: goals,
        batches and subtasks get one state per category, backlog items open,
        done and dropped; every state is named after its category.

        Returns:
            - definition (WorkflowDefinition): the default definition.
        """
        work = _one_state_per(tuple(Category))
        backlog = _one_state_per(BACKLOG_CATEGORIES)
        return cls(
            kinds={
                kind: backlog if kind is ItemKind.BACKLOG else work for kind in ItemKind
            }
        )

    def for_kind(self, kind: ItemKind) -> KindWorkflow:
        """
        Return the workflow for one item kind.

        Args:
            - kind (ItemKind): the item kind.

        Returns:
            - workflow (KindWorkflow): that kind's states and rules.
        """
        return self.kinds[kind]


def _one_state_per(categories: tuple[Category, ...]) -> KindWorkflow:
    """A kind workflow with one state per category, named after it."""
    return KindWorkflow(
        states=tuple(StateSpec(name=c.value, category=c) for c in categories),
        defaults={c: c.value for c in REQUIRED_DEFAULTS},
    )
