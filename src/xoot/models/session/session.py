"""A stored session row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, Timestamp, Title
from xoot.models.session.client import Client
from xoot.models.session.session_status import SessionStatus


class Session(BaseModel):
    """
    One working session in a project. Writes made within it link the items
    they touch; closing it requires a disposition for each open linked item.
    start_seq and close_seq come from the project's sequence counter and
    decide ordering; started_at and closed_at are for display only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    project_id: Id
    number: Id
    client: Client
    title: Title
    status: SessionStatus
    summary: Body | None
    start_seq: Id
    close_seq: Id | None
    started_at: Timestamp
    closed_at: Timestamp | None
