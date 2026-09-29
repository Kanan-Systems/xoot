"""The context every mutating service call carries."""

from pydantic import BaseModel, ConfigDict

from xoot.models.event.actor import Actor


class WriteContext(BaseModel):
    """The actor behind a write: who, and through which client."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor: Actor
