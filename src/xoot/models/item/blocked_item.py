"""A goal or batch that would be complete but for its open backlog."""

from pydantic import BaseModel, ConfigDict, Field


class BlockedItem(BaseModel):
    """Every child is done or dropped, yet open_backlog items still sit on it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    open_backlog: int = Field(ge=1)
