"""The actor recorded on events and reported in version conflicts."""

from pydantic import BaseModel, ConfigDict

from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client


class Actor(BaseModel):
    """Who made a write (Claude or the user) and through which client."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ActorKind
    client: Client
