"""What item_update returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.literals import Phase, UpdateMode
from xoot.server.schemas.subtree_output import SubtreeOutput


class ItemUpdateOutput(BaseModel):
    """
    mode is the path taken. A direct update returns the item. A drop or
    reparent of an item with children first returns a preview plan and a
    confirm_token, then the applied plan.
    """

    model_config = ConfigDict(frozen=True)

    mode: UpdateMode
    phase: Phase
    confirm_token: str | None
    item: ItemDetail | None
    plan: SubtreeOutput | None
