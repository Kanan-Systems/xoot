"""What GET /api/v1/projects/{prefix}/sessions/{key} returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.session_summary import SessionSummary


class SessionView(BaseModel):
    """
    One session, its close summary, and the keys of the items it is linked
    to, which the tree overlay highlights.
    """

    model_config = ConfigDict(frozen=True)

    session: SessionSummary
    summary: str | None
    items: list[str]
