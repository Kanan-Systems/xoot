"""One open session's backlog, as the backlogs view lists it."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.session_summary import SessionSummary


class SessionBacklogEntry(BaseModel):
    """An open session and the items parked in its backlog."""

    model_config = ConfigDict(frozen=True)

    session: SessionSummary
    items: list[ItemSummary]
    truncated: bool
