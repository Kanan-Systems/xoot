"""What a redaction returns."""

from pydantic import BaseModel, ConfigDict

from xoot.models.event.entity_type import EntityType
from xoot.models.event.redactable_field import RedactableField
from xoot.models.fields import Id


class RedactionResult(BaseModel):
    """
    The redacted entity and field, the row's new version (None for sessions
    and projects, which have none), the events whose before/after were
    rewritten, and whether the WAL checkpoint completed.

    purged is False when another connection kept the checkpoint from
    truncating the WAL: the redaction is committed, but older copies of the
    text may remain in the WAL file until a later checkpoint.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: EntityType
    entity_id: Id
    field: RedactableField
    version: Id | None
    redacted_event_ids: tuple[Id, ...]
    purged: bool
