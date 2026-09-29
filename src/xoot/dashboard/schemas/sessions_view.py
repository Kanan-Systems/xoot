"""What GET /api/v1/projects/{prefix}/sessions returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.session_summary import SessionSummary


class SessionsView(BaseModel):
    """Sessions, open ones first, then newest first."""

    model_config = ConfigDict(frozen=True)

    project: str
    sessions: list[SessionSummary]
    truncated: bool
