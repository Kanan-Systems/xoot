"""What backlog_list returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.backlog_entry import BacklogEntry
from xoot.server.schemas.literals import ResolvedBy


class BacklogOutput(BaseModel):
    """
    Backlog items, project level first, then by key; truncated when the cap
    hid items. at is the goal or batch whose own backlog was asked for.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    resolved_by: ResolvedBy
    at: str | None
    items: list[BacklogEntry]
    truncated: bool
