"""A decision row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Id, Timestamp, Title


class NewDecision(BaseModel):
    """
    Every decision column the service decides; id and version come from the
    DB. number is allocated by the owner item.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Id
    owner_item_id: Id
    number: Id
    title: Title
    body: Body
    status: DecisionStatus
    supersedes_id: Id | None
    created_at: Timestamp
