"""Query parameters of GET /api/v1/projects/{prefix}/sessions."""

from pydantic import BaseModel, ConfigDict

from xoot.models.session.session_status import SessionStatus


class SessionsParams(BaseModel):
    """An optional status filter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SessionStatus | None = None
