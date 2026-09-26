"""A stored session row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, Timestamp, Title
from xoot.models.session.client import Client
from xoot.models.session.session_status import SessionStatus


class Session(BaseModel):
    """
    One working session in a project. Writes made within it link the items
    they touch; closing it requires a disposition for each open linked item.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    project_id: Id
    number: Id
    client: Client
    title: Title
    status: SessionStatus
    summary: Body | None
    started_at: Timestamp
    closed_at: Timestamp | None
