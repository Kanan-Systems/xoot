"""The planned effect of a bulk create."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Sha256Hex
from xoot.models.item.planned_item import PlannedItem


class BulkPlan(BaseModel):
    """
    Every item the bulk create would insert, in insert order. Keys are
    planned from the parents' counters; the apply reports the keys actually
    assigned. plan_sha256 digests the post-apply entry of every planned
    item.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    items: tuple[PlannedItem, ...]
    plan_sha256: Sha256Hex
