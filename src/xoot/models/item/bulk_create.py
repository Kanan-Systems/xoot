"""Input for creating a tree of new items in one transaction."""

from collections.abc import Iterator
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xoot.models.item.bulk_item import BulkItem

MAX_BULK_ITEMS = 50
# The most items one move, push or drop plan may change; larger subtrees are
# refused at plan time rather than written in one long transaction.
MAX_PLAN_ITEMS = 200


class BulkCreate(BaseModel):
    """
    Top-level nodes of a bulk create, at most MAX_BULK_ITEMS items in total
    counting every nested node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[BulkItem, ...] = Field(min_length=1, max_length=MAX_BULK_ITEMS)

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        """Cap the total size and keep parent_id to top-level nodes."""
        nodes = list(self.walk())
        if len(nodes) > MAX_BULK_ITEMS:
            raise ValueError(f"at most {MAX_BULK_ITEMS} items per bulk create")
        if any(
            node.parent_id is not None for node, parent in nodes if parent is not None
        ):
            raise ValueError("only top-level items may name an existing parent")
        return self

    def walk(self) -> Iterator[tuple[BulkItem, int | None]]:
        """
        Yield every node in pre-order with the position of its parent node.

        Pre-order is the insert order, so each parent is inserted before its
        children and keys are assigned in reading order.

        Returns:
            - nodes (Iterator[tuple[BulkItem, int | None]]): the node and the
              pre-order position of its parent node, None for top-level nodes.
        """
        stack: list[tuple[BulkItem, int | None]] = [
            (node, None) for node in reversed(self.items)
        ]
        position = 0
        while stack:
            node, parent = stack.pop()
            yield node, parent
            stack.extend((child, position) for child in reversed(node.children))
            position += 1
