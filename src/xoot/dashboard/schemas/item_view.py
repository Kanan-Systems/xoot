"""GET /api/v1/projects/{p}/items/{key}."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.decision_detail import DecisionDetail
from xoot.server.schemas.event_entry import EventEntry
from xoot.server.schemas.item_detail import ItemDetail


class ItemView(BaseModel):
    """
    One item in full: its children (work first, then backlog), its most
    recent events (newest first) and the decisions made on it, with bodies.
    """

    model_config = ConfigDict(frozen=True)

    item: ItemDetail
    children: ChildrenSummary
    events: list[EventEntry]
    decisions: list[DecisionDetail]
