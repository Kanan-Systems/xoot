"""Input for creating an item."""

from xoot.models.fields import Id, StateName
from xoot.models.item.item_basics import ItemBasics


class ItemCreate(ItemBasics):
    """
    A new item. state defaults to the kind's default open state. The backlog
    links are set by the services only: found_on_item_id by capture,
    origin_item_id by backlog_cover.
    """

    state: StateName | None = None
    awaiting_decision_id: Id | None = None
    found_on_item_id: Id | None = None
    origin_item_id: Id | None = None
