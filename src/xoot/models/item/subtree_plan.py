"""The planned effect of a subtree drop or reparent."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Sha256Hex
from xoot.models.item.item_change import ItemChange


class SubtreePlan(BaseModel):
    """
    changes lists every row that will be written. carried_item_ids lists
    descendants that move with the root without their own row changing.
    plan_sha256 digests the affected keys and their target states, so an
    apply can tell whether the plan still matches its preview.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_id: Id
    changes: tuple[ItemChange, ...]
    carried_item_ids: tuple[Id, ...]
    plan_sha256: Sha256Hex
