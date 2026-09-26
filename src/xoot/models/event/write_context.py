"""The context every mutating service call carries."""

from pydantic import BaseModel, ConfigDict

from xoot.models.event.actor import Actor
from xoot.models.fields import Id


class WriteContext(BaseModel):
    """
    The actor behind a write and, optionally, the session it belongs to.

    When session_id is set the session must be open and in the same project,
    and every item the write touches is linked to it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor: Actor
    session_id: Id | None = None
