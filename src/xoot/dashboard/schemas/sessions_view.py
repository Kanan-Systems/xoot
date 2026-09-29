"""What GET /api/v1/projects/{prefix}/sessions returns."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.session_row import SessionRow


class SessionsView(BaseModel):
    """Sessions, open ones first, then newest first."""

    model_config = ConfigDict(frozen=True)

    project: str
    sessions: list[SessionRow]
    truncated: bool
