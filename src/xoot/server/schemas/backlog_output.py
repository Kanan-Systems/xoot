"""What backlog_list returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import BacklogScope, ResolvedBy


class BacklogOutput(BaseModel):
    """Backlog items by number; truncated when the cap hid items."""

    model_config = ConfigDict(frozen=True)

    project: str
    resolved_by: ResolvedBy
    scope: BacklogScope
    items: list[ItemSummary]
    truncated: bool
