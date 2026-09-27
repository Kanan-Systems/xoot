"""What item_get returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.event_entry import EventEntry
from xoot.server.schemas.item_detail import ItemDetail


class ItemGetOutput(BaseModel):
    """The item, its children and its most recent events, newest first."""

    model_config = ConfigDict(frozen=True)

    item: ItemDetail
    children: ChildrenSummary
    events: list[EventEntry]
