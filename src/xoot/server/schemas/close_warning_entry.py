"""A session close preview warning."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.category import Category


class CloseWarningEntry(BaseModel):
    """An item left live under a parent that is or will be backlogged or dropped."""

    model_config = ConfigDict(frozen=True)

    key: str
    parent: str
    parent_category: Category
