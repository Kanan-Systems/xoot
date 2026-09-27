"""The fields every way of creating an item shares."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, Title
from xoot.models.item.item_kind import ItemKind


class ItemBasics(BaseModel):
    """What a caller chooses for any new item: kind, title, body and parent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ItemKind
    title: Title
    body: Body = ""
    parent_id: Id | None = None
