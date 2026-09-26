"""A stored item row: a goal, batch or subtask."""

from xoot.models.fields import Id, Timestamp
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.new_item import NewItem


class Item(NewItem):
    """
    One tracked unit of work: the inserted columns plus the id, version and
    updated_at the database maintains. key is "<prefix>-<number>". version
    increases on every change and backs optimistic concurrency.
    """

    id: Id
    version: Id
    updated_at: Timestamp

    @property
    def unfiled(self) -> bool:
        """A subtask with no parent batch. Derived, never stored."""
        return self.kind is ItemKind.SUBTASK and self.parent_id is None
