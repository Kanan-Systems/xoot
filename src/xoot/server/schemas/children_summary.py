"""The direct children of an item, summarized."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.category import Category
from xoot.server.schemas.item_summary import ItemSummary


class ChildrenSummary(BaseModel):
    """How many children there are per category, and the first few of them."""

    model_config = ConfigDict(frozen=True)

    total: int
    by_category: dict[Category, int]
    items: list[ItemSummary]
    truncated: bool
