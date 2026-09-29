"""One item in a tree query result."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.item import Item


class TreeNode(BaseModel):
    """An item and its depth below the query roots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Item
    depth: int = Field(ge=0)
