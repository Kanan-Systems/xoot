"""Input for closing a session."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Body, Id
from xoot.models.session.disposition import Disposition

MAX_DISPOSITIONS = 1000


class SessionClose(BaseModel):
    """An optional summary and a disposition per open linked item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: Body | None = None
    dispositions: dict[Id, Disposition] = Field(
        default_factory=dict, max_length=MAX_DISPOSITIONS
    )
