"""A stored link between a session and an item."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Timestamp
from xoot.models.session.disposition import Disposition


class SessionItemRef(BaseModel):
    """An item a session touched; disposition is set when the session closes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: Id
    item_id: Id
    project_id: Id
    linked_at: Timestamp
    disposition: Disposition | None
