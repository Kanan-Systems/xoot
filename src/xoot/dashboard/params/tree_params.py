"""Query parameters of GET /api/v1/projects/{prefix}/tree."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.tree_query import MAX_DEPTH, MAX_ITEMS


class TreeParams(BaseModel):
    """
    Where the tree starts and how much of it to return; the same bounds and
    defaults as tree_get.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root: str | None = Field(default=None, max_length=64)
    depth: int = Field(default=3, ge=0, le=MAX_DEPTH)
    include_done: bool = False
    limit: int = Field(default=200, ge=1, le=MAX_ITEMS)
