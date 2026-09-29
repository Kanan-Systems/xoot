"""A stored item row: a goal, batch, subtask or backlog item."""

from xoot.models.fields import Id, Timestamp
from xoot.models.item.new_item import NewItem


class Item(NewItem):
    """
    One tracked unit: the inserted columns plus the id, version and
    updated_at the database maintains. key is unique within the project and
    changes only when the item moves; version increases on every change and
    backs optimistic concurrency. The numbering counters are not part of it.
    """

    id: Id
    version: Id
    updated_at: Timestamp
