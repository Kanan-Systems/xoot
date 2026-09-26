"""A decision row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Id, Timestamp, Title


class NewDecision(BaseModel):
    """Every decision column the service decides; id and version come from the DB."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    number: Id
    key: str
    title: Title
    body: Body
    status: DecisionStatus
    supersedes_id: Id | None
    scope_item_id: Id | None
    created_at: Timestamp
