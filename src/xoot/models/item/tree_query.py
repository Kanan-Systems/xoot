"""Input for a bounded tree query."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Id

MAX_DEPTH = 8
MAX_ITEMS = 1000


class TreeQuery(BaseModel):
    """
    Which part of a project's tree to return. Without root_id the tree
    starts at goals and unfiled subtasks. Done and dropped items (and
    everything under them) are left out unless include_terminal is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_id: Id | None = None
    depth: int = Field(default=3, ge=0, le=MAX_DEPTH)
    max_items: int = Field(default=200, ge=1, le=MAX_ITEMS)
    include_terminal: bool = False
