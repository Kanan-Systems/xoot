"""An item as it appears in lists and trees."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category


class ItemSummary(BaseModel):
    """
    Enough to recognize, pick and update an item. key is its nested path
    within the project; category is the fixed meaning of the
    project-defined state; version is what item_update needs.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    kind: ItemKind
    title: str
    state: str
    category: Category | None
    parent: str | None
    version: int
