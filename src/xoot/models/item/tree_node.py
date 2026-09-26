"""One item in a tree query result."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.item import Item


class TreeNode(BaseModel):
    """An item, its depth below the query roots, and whether it is unfiled."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Item
    depth: int = Field(ge=0)
    unfiled: bool
