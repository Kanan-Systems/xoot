"""What GET /api/v1/projects/{prefix}/sessions/{key} returns."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.session_item_entry import SessionItemEntry
from xoot.server.schemas.session_summary import SessionSummary


class SessionView(BaseModel):
    """
    One session, its close summary, the keys of the items it is linked to
    (which the tree filter uses) and those items with their outcomes.
    """

    model_config = ConfigDict(frozen=True)

    session: SessionSummary
    summary: str | None
    items: list[str]
    linked: list[SessionItemEntry]
