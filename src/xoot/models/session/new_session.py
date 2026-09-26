"""A session row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Timestamp, Title
from xoot.models.session.client import Client


class NewSession(BaseModel):
    """Every column of a new open session except the id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    number: Id
    client: Client
    title: Title
    started_at: Timestamp
