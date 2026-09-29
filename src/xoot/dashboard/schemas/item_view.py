"""What GET /api/v1/items/{key} returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.decision_detail import DecisionDetail
from xoot.server.schemas.event_entry import EventEntry
from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.session_summary import SessionSummary


class ItemView(BaseModel):
    """
    One item in full: its children, most recent events (newest first), the
    sessions it is linked to and the decisions scoped to it, with bodies.
    """

    model_config = ConfigDict(frozen=True)

    item: ItemDetail
    children: ChildrenSummary
    events: list[EventEntry]
    sessions: list[SessionSummary]
    decisions: list[DecisionDetail]
