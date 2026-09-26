"""An event row about to be appended."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event_action import EventAction
from xoot.models.fields import Id, Timestamp
from xoot.models.session.client import Client


class NewEvent(BaseModel):
    """Every event column except the id the database assigns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    entity_type: EntityType
    entity_id: Id
    action: EventAction
    actor_kind: ActorKind
    client: Client
    session_id: Id | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: Timestamp
