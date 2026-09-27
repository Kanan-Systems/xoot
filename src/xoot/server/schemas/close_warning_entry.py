"""A session close preview warning."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.category import Category


class CloseWarningEntry(BaseModel):
    """An item left live under a parent that is or will be backlogged or dropped."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["parent_state"] = "parent_state"
    key: str
    parent: str
    parent_category: Category
