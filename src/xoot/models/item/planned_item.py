"""One item a bulk create preview plans to insert."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Title
from xoot.models.item.item_kind import ItemKind


class PlannedItem(BaseModel):
    """
    The key the item would get if nothing else is created first, and its
    parent's key, which is either an existing item or an earlier planned one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    kind: ItemKind
    title: Title
    parent_key: str | None
