"""One node of a bulk create: an item and the new items nested under it."""

from pydantic import Field

from xoot.models.item.item_basics import ItemBasics

MAX_CHILDREN = 50


class BulkItem(ItemBasics):
    """
    A new goal, batch or subtask with its new children. parent_id names an
    existing parent and is only allowed on top-level nodes; nested nodes sit
    under their node. Every item starts in its kind's default open state.
    """

    children: tuple["BulkItem", ...] = Field(default=(), max_length=MAX_CHILDREN)
