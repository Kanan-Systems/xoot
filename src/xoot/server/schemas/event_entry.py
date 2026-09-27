"""One event from an item's history."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.event_action import EventAction
from xoot.models.session.client import Client


class EventEntry(BaseModel):
    """
    Who changed what and when. changed names every changed field, body
    included; before/after hold the non-body values, with keys for references.
    """

    model_config = ConfigDict(frozen=True)

    action: EventAction
    actor_kind: ActorKind
    client: Client
    session: str | None
    created_at: str
    redacted: bool
    changed: list[str]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
