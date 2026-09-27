"""The planned effect of a bulk create."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id
from xoot.models.item.planned_item import PlannedItem


class BulkPlan(BaseModel):
    """
    Every item the bulk create would insert, in insert order. Keys are
    planned from the project's counter; the apply reports the keys actually
    assigned.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: Id
    items: tuple[PlannedItem, ...]
