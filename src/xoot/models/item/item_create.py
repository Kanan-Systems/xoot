"""Input for creating an item."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, StateName, Title
from xoot.models.item.item_kind import ItemKind


class ItemCreate(BaseModel):
    """
    A new item. state defaults to the kind's default open state;
    backlog_session_id is only valid with a backlogged state.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ItemKind
    title: Title
    body: Body = ""
    parent_id: Id | None = None
    state: StateName | None = None
    backlog_session_id: Id | None = None
    awaiting_decision_id: Id | None = None
