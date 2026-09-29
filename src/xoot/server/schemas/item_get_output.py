"""What item_get returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.event_entry import EventEntry
from xoot.server.schemas.item_detail import ItemDetail


class ItemGetOutput(BaseModel):
    """
    The item, its children (work first, then backlog), the decisions made
    on it, and its most recent events, newest first.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    item: ItemDetail
    children: ChildrenSummary
    decisions: list[DecisionSummary]
    events: list[EventEntry]
