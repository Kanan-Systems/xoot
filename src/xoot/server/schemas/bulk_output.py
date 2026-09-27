"""What items_create_bulk returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import Phase
from xoot.server.schemas.planned_entry import PlannedEntry


class BulkOutput(BaseModel):
    """
    A preview lists the planned items and a confirm_token; an apply lists
    the created items with the keys they actually got.
    """

    model_config = ConfigDict(frozen=True)

    phase: Phase
    confirm_token: str | None
    planned: list[PlannedEntry]
    created: list[ItemSummary]
