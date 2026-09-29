"""An item row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Id, StateName, Timestamp, Title
from xoot.models.item.item_kind import ItemKind


class NewItem(BaseModel):
    """
    Every item column the service decides; id and version come from the DB.
    key is the nested path built from the parent's key and number.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    kind: ItemKind
    number: Id
    key: str
    parent_id: Id | None
    title: Title
    body: Body
    state: StateName
    found_on_item_id: Id | None
    covered_by_item_id: Id | None
    origin_item_id: Id | None
    awaiting_decision_id: Id | None
    created_at: Timestamp
