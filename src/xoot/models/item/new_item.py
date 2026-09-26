"""An item row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, StateName, Timestamp, Title
from xoot.models.item.item_kind import ItemKind


class NewItem(BaseModel):
    """Every item column the service decides; id and version come from the DB."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    number: Id
    key: str
    kind: ItemKind
    parent_id: Id | None
    title: Title
    body: Body
    state: StateName
    backlog_session_id: Id | None
    awaiting_decision_id: Id | None
    created_at: Timestamp
