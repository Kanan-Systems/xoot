"""Query parameters of GET /api/v1/projects/{p}/tree."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.tree_query import MAX_DEPTH, MAX_ITEMS
from xoot.utils.keys import KEY_MAX


class TreeParams(BaseModel):
    """
    Which goal the tree starts at (the whole project when omitted) and how
    much of it to return; the same bounds and defaults as tree_get.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal: str | None = Field(default=None, max_length=KEY_MAX)
    depth: int = Field(default=3, ge=0, le=MAX_DEPTH)
    include_done: bool = False
    limit: int = Field(default=200, ge=1, le=MAX_ITEMS)
