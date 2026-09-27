"""A non-blocking warning returned by a session close preview."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id
from xoot.models.workflow.category import Category


class CloseWarning(BaseModel):
    """
    An item whose disposition leaves it live under a parent that is, or will
    be, backlogged or dropped. Parent and child states stay independent, so
    the close is still allowed; the warning only points it out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: Id
    key: str
    parent_id: Id
    parent_key: str
    parent_category: Category
