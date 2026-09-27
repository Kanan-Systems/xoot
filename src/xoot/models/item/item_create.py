"""Input for creating an item."""

from xoot.models.fields import Id, StateName
from xoot.models.item.item_basics import ItemBasics


class ItemCreate(ItemBasics):
    """
    A new item. state defaults to the kind's default open state;
    backlog_session_id is only valid with a backlogged state.
    """

    state: StateName | None = None
    backlog_session_id: Id | None = None
    awaiting_decision_id: Id | None = None
