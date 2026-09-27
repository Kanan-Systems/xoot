"""One node of the items argument of items_create_bulk."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Body, Title
from xoot.models.item.bulk_item import MAX_CHILDREN
from xoot.models.item.item_kind import ItemKind


class BulkItemInput(BaseModel):
    """
    A new item and the new items under it: goals hold batches, batches hold
    subtasks. Only top-level nodes may name an existing parent by key.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ItemKind
    title: Title
    body: Body = ""
    parent: str | None = Field(
        default=None, description="Existing parent item key; top-level nodes only."
    )
    children: list["BulkItemInput"] = Field(
        default_factory=list, max_length=MAX_CHILDREN
    )
