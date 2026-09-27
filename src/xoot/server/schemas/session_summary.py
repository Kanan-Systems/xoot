"""A session as tools report it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.session.client import Client
from xoot.models.session.session_status import SessionStatus


class SessionSummary(BaseModel):
    """A session's key, title, client, status and timestamps."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    client: Client
    status: SessionStatus
    started_at: str
    closed_at: str | None
