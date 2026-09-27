"""One node of a tree_get result."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.item_summary import ItemSummary


class TreeEntry(BaseModel):
    """An item and its depth below the query's roots."""

    model_config = ConfigDict(frozen=True)

    depth: int
    unfiled: bool
    item: ItemSummary
